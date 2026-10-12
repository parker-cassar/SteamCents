from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api import db
from steamprice import config
from steamprice.public_filter import diversify_drops, is_blocked_name, sql_exclude_name

app = FastAPI(title="steamcents", description="steam price history, read only")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.API_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    try:
        db.one("SELECT 1 AS ok")
    except Exception:
        raise HTTPException(status_code=503, detail="database unreachable")
    return {"ok": True}


@app.get("/stats")
def stats():
    catalog = db.one("""
        SELECT count(*) AS apps,
               count(*) FILTER (WHERE delisted_at IS NULL) AS live,
               count(*) FILTER (WHERE last_checked_at IS NOT NULL
                                AND delisted_at IS NULL) AS checked,
               count(*) FILTER (WHERE no_price_seen_at IS NOT NULL) AS unpriced,
               count(*) FILTER (WHERE consecutive_failures >= %s) AS parked
        FROM apps
    """, (config.MAX_FAILURES,))

    prices = db.one("""
        SELECT count(*) AS observations,
               count(DISTINCT appid) AS apps_with_price,
               min(observed_at) AS first_observed,
               max(observed_at) AS last_observed
        FROM price_observations
    """)

    sweep = db.one("""
        SELECT id, started_at, heartbeat_at, ended_at, exit_reason,
               batches, apps_checked, changes, http_429s, errors,
               extract(epoch FROM now() - heartbeat_at) AS heartbeat_age_s
        FROM sweep_runs ORDER BY id DESC LIMIT 1
    """)

    catalog_run = db.one("""
        SELECT id, started_at, exit_reason, remote_apps, live, newly_delisted
        FROM catalog_runs WHERE exit_reason = 'ok' ORDER BY id DESC LIMIT 1
    """)

    totals = db.one("""
        SELECT coalesce(sum(apps_checked), 0) AS checks,
               coalesce(sum(changes), 0) AS changes,
               coalesce(sum(http_429s), 0) AS http_429s,
               coalesce(sum(errors), 0) AS errors,
               min(started_at) AS tracked_since
        FROM sweep_runs
    """)

    days = None
    if prices["first_observed"] and prices["last_observed"]:
        days = round(
            (prices["last_observed"] - prices["first_observed"]).total_seconds() / 86400, 2
        )

    live = catalog["live"] or 1
    # checked counts live apps only, so this cannot run past 100
    return {
        "catalog": catalog,
        "prices": dict(prices, days_of_history=days),
        "coverage_pct": round(100.0 * catalog["checked"] / live, 2),
        "sweep": sweep,
        "catalog_run": catalog_run,
        "totals": totals,
        "tiers": db.rows(
            "SELECT tier, count(*) AS apps FROM apps WHERE delisted_at IS NULL "
            "GROUP BY tier ORDER BY tier"
        ),
    }


@app.get("/apps/{appid}")
def get_app(appid: int):
    row = db.one("""
        SELECT a.appid, a.name, a.delisted_at, a.last_checked_at, a.last_changed_at,
               a.no_price_seen_at, a.tier, a.next_due_at,
               p.currency, p.initial_cents, p.final_cents, p.discount_pct, p.observed_at
        FROM apps a
        LEFT JOIN app_latest_price p ON p.appid = a.appid AND p.country_code = %s
        WHERE a.appid = %s
    """, (config.COUNTRY, appid))
    if row is None or is_blocked_name(row.get("name")):
        raise HTTPException(status_code=404, detail="unknown appid")
    return row


@app.get("/apps/{appid}/history")
def history(
    appid: int,
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    row = db.one("SELECT name FROM apps WHERE appid = %s", (appid,))
    if row is None or is_blocked_name(row.get("name")):
        raise HTTPException(status_code=404, detail="unknown appid")
    return {
        "appid": appid,
        "limit": limit,
        "offset": offset,
        "observations": db.rows("""
            SELECT observed_at, currency, initial_cents, final_cents, discount_pct
            FROM price_observations
            WHERE appid = %s AND country_code = %s
            ORDER BY observed_at
            LIMIT %s OFFSET %s
        """, (appid, config.COUNTRY, limit, offset)),
    }


@app.get("/changes")
def changes(
    since: datetime | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    return {
        "since": since,
        "limit": limit,
        "offset": offset,
        "changes": db.rows(f"""
            SELECT c.appid, a.name, c.observed_at, c.currency,
                   c.prev_final_cents, c.final_cents, c.discount_pct
            FROM price_changes c
            JOIN apps a USING (appid)
            WHERE c.prev_final_cents IS NOT NULL
              AND c.country_code = %s
              AND (%s::timestamptz IS NULL OR c.observed_at >= %s)
              AND {sql_exclude_name("a.name")}
            ORDER BY c.observed_at DESC
            LIMIT %s OFFSET %s
        """, (config.COUNTRY, since, since, limit, offset)),
    }


@app.get("/changes/daily")
def changes_daily(days: int = Query(30, ge=1, le=365)):
    return {
        "days": days,
        "series": db.rows("""
            SELECT day, changes, drops, rises, apps
            FROM price_changes_daily
            WHERE country_code = %s AND day >= current_date - %s::int
            ORDER BY day
        """, (config.COUNTRY, days)),
    }


@app.get("/drops")
def drops(
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    target = limit + offset
    # overfetch so family caps and interleave still fill the page
    pool = max(target * 8, 200)

    # only window apps that moved recently. the old price_drops view ran
    # lag() over the entire observations table on every request.
    latest = db.rows(f"""
        WITH recent_apps AS (
            SELECT DISTINCT appid
            FROM price_observations
            WHERE country_code = %s
              AND observed_at >= now() - make_interval(days => %s)
        ),
        scoped AS (
            SELECT
                o.appid, o.country_code, o.observed_at, o.currency,
                o.final_cents, o.discount_pct,
                lag(o.final_cents) OVER w AS prev_final_cents
            FROM price_observations o
            JOIN recent_apps r USING (appid)
            WHERE o.country_code = %s
            WINDOW w AS (PARTITION BY o.appid ORDER BY o.observed_at)
        ),
        drops AS (
            SELECT
                s.appid, a.name, s.observed_at, s.currency,
                s.prev_final_cents, s.final_cents, s.discount_pct,
                s.prev_final_cents - s.final_cents AS drop_cents,
                round(
                    100.0 * (s.prev_final_cents - s.final_cents)
                    / s.prev_final_cents, 1
                ) AS drop_pct
            FROM scoped s
            JOIN apps a USING (appid)
            WHERE s.prev_final_cents IS NOT NULL
              AND s.prev_final_cents > 0
              AND s.final_cents < s.prev_final_cents
              AND s.observed_at >= now() - make_interval(days => %s)
              AND {sql_exclude_name("a.name")}
        )
        SELECT DISTINCT ON (appid)
               appid, name, observed_at, currency,
               prev_final_cents, final_cents, discount_pct,
               drop_cents, drop_pct
        FROM drops
        ORDER BY appid, observed_at DESC
    """, (config.COUNTRY, days, config.COUNTRY, days))

    by_savings = sorted(
        latest,
        key=lambda r: (r["drop_cents"], float(r["drop_pct"]), r["observed_at"]),
        reverse=True,
    )[:pool]
    by_percent = sorted(
        latest,
        key=lambda r: (float(r["drop_pct"]), r["drop_cents"], r["observed_at"]),
        reverse=True,
    )[:pool]
    balanced = diversify_drops(by_savings, by_percent, target)

    return {
        "days": days,
        "limit": limit,
        "offset": offset,
        "drops": balanced[offset:target],
    }


@app.get("/briefs/latest")
def briefs_latest():
    row = db.one("""
        SELECT id, period_start, period_end, brief_json, model, prompt_version, created_at
        FROM briefs
        ORDER BY created_at DESC
        LIMIT 1
    """)
    if row is None:
        raise HTTPException(status_code=404, detail="no briefs yet")
    return {
        "id": row["id"],
        "period_start": row["period_start"],
        "period_end": row["period_end"],
        "brief": row["brief_json"],
        "model": row["model"],
        "prompt_version": row["prompt_version"],
        "created_at": row["created_at"],
    }
