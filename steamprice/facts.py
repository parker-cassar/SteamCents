from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from steamprice import config
from steamprice.public_filter import sql_exclude_name


def _jsonable(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return v


def _row(d):
    return {k: _jsonable(v) for k, v in d.items()}


def build_facts(cur, days=None, drop_limit=15):
    days = days if days is not None else config.BRIEF_DAYS
    country = config.COUNTRY

    cur.execute("""
        SELECT count(*) AS apps,
               count(*) FILTER (WHERE delisted_at IS NULL) AS live,
               count(*) FILTER (WHERE last_checked_at IS NOT NULL
                                AND delisted_at IS NULL) AS checked,
               count(*) FILTER (WHERE no_price_seen_at IS NOT NULL) AS unpriced,
               count(*) FILTER (WHERE consecutive_failures >= %s) AS parked
        FROM apps
    """, (config.MAX_FAILURES,))
    catalog = _row(dict(zip(
        ("apps", "live", "checked", "unpriced", "parked"), cur.fetchone()
    )))

    cur.execute("""
        SELECT count(*) AS observations,
               count(DISTINCT appid) AS apps_with_price,
               min(observed_at) AS first_observed,
               max(observed_at) AS last_observed
        FROM price_observations
    """)
    prices = _row(dict(zip(
        ("observations", "apps_with_price", "first_observed", "last_observed"),
        cur.fetchone(),
    )))

    live = catalog["live"] or 1
    catalog["coverage_pct"] = round(100.0 * catalog["checked"] / live, 2)

    cur.execute("""
        SELECT coalesce(sum(apps_checked), 0), coalesce(sum(changes), 0),
               coalesce(sum(http_429s), 0), coalesce(sum(errors), 0)
        FROM sweep_runs
        WHERE started_at >= now() - make_interval(days => %s)
    """, (days,))
    checks, changes, http_429s, errors = cur.fetchone()
    period = {
        "days": days,
        "checks": int(checks),
        "changes": int(changes),
        "http_429s": int(http_429s),
        "errors": int(errors),
    }

    cur.execute("""
        SELECT day, changes, drops, rises, apps
        FROM price_changes_daily
        WHERE country_code = %s AND day >= current_date - %s::int
        ORDER BY day
    """, (country, days))
    daily = [
        _row(dict(zip(("day", "changes", "drops", "rises", "apps"), r)))
        for r in cur.fetchall()
    ]

    cur.execute(f"""
        SELECT appid, name, observed_at, currency,
               prev_final_cents, final_cents, discount_pct, drop_cents, drop_pct
        FROM price_drops
        WHERE country_code = %s AND observed_at >= now() - make_interval(days => %s)
          AND {sql_exclude_name("name")}
        ORDER BY drop_pct DESC, drop_cents DESC
        LIMIT %s
    """, (country, days, drop_limit))
    cols = (
        "appid", "name", "observed_at", "currency", "prev_final_cents",
        "final_cents", "discount_pct", "drop_cents", "drop_pct",
    )
    drops = [_row(dict(zip(cols, r))) for r in cur.fetchall()]

    today = date.today()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_start": (today - timedelta(days=days)).isoformat(),
        "period_end": today.isoformat(),
        "country": country,
        "catalog": catalog,
        "prices": prices,
        "period": period,
        "daily_changes": daily,
        "top_drops": drops,
    }
