import signal
import sys
import threading
import urllib.error
from datetime import datetime, timezone

from steamprice import config, db, schedule
from steamprice.log import setup
from steamprice.steam import answered, fetch_appdetails, parse_price

MAX_FAILURES = config.MAX_FAILURES
IDLE_SLEEP = 60.0

STOP = threading.Event()


def nap(seconds):
    # wakes early on sigterm so a long backoff does not hold up shutdown
    STOP.wait(seconds)

CLAIM = """
SELECT appid
FROM apps
WHERE delisted_at IS NULL AND next_due_at <= now()
ORDER BY next_due_at, appid
LIMIT %s
"""

LAST_PRICES = """
SELECT DISTINCT ON (appid)
  appid, currency, initial_cents, final_cents, discount_pct
FROM price_observations
WHERE country_code = %s AND appid = ANY(%s)
ORDER BY appid, observed_at DESC
"""

INSERT_OBS = """
INSERT INTO price_observations (
  appid, country_code, observed_at,
  currency, initial_cents, final_cents, discount_pct
) VALUES (%s, %s, now(), %s, %s, %s, %s)
"""


def claim(cur, n):
    cur.execute(CLAIM, (n,))
    return [r[0] for r in cur.fetchall()]


def start_run(conn):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO sweep_runs DEFAULT VALUES RETURNING id")
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def beat(conn, run_id, batches, checks, changes, http_429, errors):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE sweep_runs
            SET heartbeat_at = now(), batches = %s, apps_checked = %s,
                changes = %s, http_429s = %s, errors = %s
            WHERE id = %s
        """, (batches, checks, changes, http_429, errors, run_id))
    conn.commit()


def end_run(run_id, reason):
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sweep_runs SET ended_at = now(), exit_reason = %s WHERE id = %s",
                (reason, run_id),
            )
        conn.commit()


def status():
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, started_at, heartbeat_at, ended_at, exit_reason,
                   batches, apps_checked, changes, http_429s, errors,
                   now() - heartbeat_at
            FROM sweep_runs ORDER BY id DESC LIMIT 5
        """)
        for r in cur.fetchall():
            state = r[4] or ("running" if r[3] is None else "?")
            print(
                f"run={r[0]} {state} started={r[1]:%Y-%m-%d %H:%M} "
                f"batches={r[5]} checks={r[6]} changes={r[7]} "
                f"429s={r[8]} errors={r[9]} last_beat={str(r[10]).split('.')[0]} ago"
            )
        cur.execute(f"SELECT count(*) FROM apps WHERE consecutive_failures >= {MAX_FAILURES}")
        print(f"parked appids: {cur.fetchone()[0]}")
        cur.execute("""
            SELECT tier, count(*), count(*) FILTER (WHERE next_due_at <= now())
            FROM apps WHERE delisted_at IS NULL GROUP BY tier ORDER BY tier
        """)
        for tier, n, due in cur.fetchall():
            print(f"tier {tier}: {n} apps, {due} due now")


def last_prices(cur, ids):
    if not ids:
        return {}
    cur.execute(LAST_PRICES, (config.COUNTRY, ids))
    out = {}
    for appid, currency, initial, final, discount in cur.fetchall():
        out[appid] = {
            "currency": currency,
            "initial_cents": initial,
            "final_cents": final,
            "discount_pct": discount,
        }
    return out


def stamp(cur, ids, missing, unpriced):
    # stamping everything, answered or not, is what stops a broken appid from
    # sitting at the front of the ordering forever
    cur.execute(
        "UPDATE apps SET last_checked_at = now() WHERE appid = ANY(%s)",
        (ids,),
    )
    missing = list(missing)
    gone = set(missing)
    ok = [i for i in ids if i not in gone]
    if ok:
        cur.execute(
            "UPDATE apps SET consecutive_failures = 0 "
            "WHERE appid = ANY(%s) AND consecutive_failures > 0",
            (ok,),
        )
    if unpriced:
        cur.execute(
            "UPDATE apps SET no_price_seen_at = now() WHERE appid = ANY(%s)",
            (list(unpriced),),
        )
    if missing:
        cur.execute(
            "UPDATE apps SET consecutive_failures = consecutive_failures + 1 "
            f"WHERE appid = ANY(%s) AND consecutive_failures < {MAX_FAILURES}",
            (missing,),
        )


def retier(cur, ids, priced, now):
    cur.execute(
        "SELECT appid, last_changed_at, consecutive_failures FROM apps WHERE appid = ANY(%s)",
        (ids,),
    )
    buckets = {}
    for appid, last_changed, failures in cur.fetchall():
        tier = schedule.classify(appid in priced, last_changed, now, failures)
        buckets.setdefault(tier, []).append(appid)
    for tier, group in buckets.items():
        cur.execute(
            "UPDATE apps SET tier = %s, next_due_at = %s WHERE appid = ANY(%s)",
            (tier, schedule.next_due(tier, now), group),
        )


def retry_after(e):
    v = getattr(e, "headers", None) and e.headers.get("Retry-After")
    try:
        return min(float(v), 300.0)
    except (TypeError, ValueError):
        return None


def changed(prev, cur):
    if prev is None:
        return True
    return (
        prev["currency"] != cur["currency"]
        or prev["initial_cents"] != cur["initial_cents"]
        or prev["final_cents"] != cur["final_cents"]
        or prev["discount_pct"] != cur["discount_pct"]
    )


def process_batch(conn, ids):
    raw = fetch_appdetails(ids)
    with conn.cursor() as cur:
        prev = last_prices(cur, ids)
        new = 0
        updated = 0
        same = 0
        missing = set()
        unpriced = set()
        priced = set()
        for appid in ids:
            entry = raw.get(str(appid))
            price = parse_price(entry)
            if price is None:
                if answered(entry):
                    unpriced.add(appid)
                else:
                    missing.add(appid)
                continue
            priced.add(appid)
            old = prev.get(appid)
            if old is not None and not changed(old, price):
                same += 1
                continue
            cur.execute(INSERT_OBS, (
                appid,
                config.COUNTRY,
                price["currency"],
                price["initial_cents"],
                price["final_cents"],
                price["discount_pct"],
            ))
            cur.execute(
                "UPDATE apps SET last_changed_at = now() WHERE appid = %s",
                (appid,),
            )
            if old is None:
                new += 1
            else:
                updated += 1
        stamp(cur, ids, missing, unpriced)
        retier(cur, ids, priced, datetime.now(timezone.utc))
    conn.commit()
    return {
        "apps": len(ids),
        "new": new,
        "updated": updated,
        "same": same,
        "unpriced": len(unpriced),
        "no_response": len(missing),
    }


def run(once=False):
    log = setup("sweep")
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: STOP.set())

    sleep_s = 60.0 / config.RATE_PER_MIN
    checks = 0
    new_total = 0
    updated_total = 0
    same_total = 0
    unpriced_total = 0
    no_response_total = 0
    http_429 = 0
    errors = 0
    streak = 0
    batches = 0
    idling = False

    with db.connect() as conn:
        run_id = start_run(conn)

    log.info(
        f"sweep start run={run_id} batch={config.BATCH_SIZE} "
        f"rate={config.RATE_PER_MIN}/min sleep={sleep_s:.1f}s cc={config.COUNTRY}"
    )

    reason = "crash"
    try:
        while True:
            if STOP.is_set():
                reason = "stopped"
                log.info(f"stopping after {batches} batches")
                break

            with db.connect() as conn:
                with conn.cursor() as cur:
                    ids = claim(cur, config.BATCH_SIZE)
                if not ids:
                    if once:
                        log.info("nothing due")
                        reason = "no work"
                        break
                    if not idling:
                        log.info(f"nothing due, checking every {IDLE_SLEEP:.0f}s")
                        idling = True
                    nap(IDLE_SLEEP)
                    continue
                idling = False

                try:
                    stats = process_batch(conn, ids)
                except (OSError, ValueError) as e:
                    if isinstance(e, urllib.error.HTTPError) and e.code == 429:
                        http_429 += 1
                        wait = retry_after(e) or sleep_s * 5
                        log.warning(f"429 backoff {wait:.0f}s ({http_429} so far)")
                        reason = "429"
                    else:
                        errors += 1
                        streak += 1
                        wait = sleep_s * 2 ** min(streak, 4)
                        log.warning(f"batch failed, {wait:.0f}s: {e}")
                        reason = "error"
                    beat(conn, run_id, batches, checks, new_total + updated_total,
                         http_429, errors)
                    if once:
                        break
                    nap(wait)
                    continue

                streak = 0
                checks += stats["apps"]
                new_total += stats["new"]
                updated_total += stats["updated"]
                same_total += stats["same"]
                unpriced_total += stats["unpriced"]
                no_response_total += stats["no_response"]
                batches += 1
                beat(conn, run_id, batches, checks, new_total + updated_total,
                     http_429, errors)

            log.info(
                f"batch={batches} apps={stats['apps']} "
                f"new={stats['new']} updated={stats['updated']} "
                f"same={stats['same']} unpriced={stats['unpriced']} "
                f"no_response={stats['no_response']} "
                f"(sum={stats['new'] + stats['updated'] + stats['same'] + stats['unpriced'] + stats['no_response']}) "
                f"429s={http_429}"
            )

            if once:
                reason = "once"
                log.info(
                    f"done new={new_total} updated={updated_total} "
                    f"same={same_total} unpriced={unpriced_total} "
                    f"no_response={no_response_total} "
                    f"(sum={new_total + updated_total + same_total + unpriced_total + no_response_total} "
                    f"of {checks})"
                )
                break

            if batches % 10 == 0:
                log.info(
                    f"summary checks={checks} new={new_total} updated={updated_total} "
                    f"same={same_total} unpriced={unpriced_total} "
                    f"no_response={no_response_total} "
                    f"429s={http_429} errors={errors}"
                )

            nap(sleep_s)
    finally:
        end_run(run_id, reason)


def main():
    if "--status" in sys.argv:
        status()
        return
    run(once="--once" in sys.argv)


if __name__ == "__main__":
    main()
