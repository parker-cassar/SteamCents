import sys
import time
import urllib.error

from steamprice import config, db
from steamprice.log import setup
from steamprice.steam import fetch_appdetails, parse_price

CLAIM = """
SELECT appid
FROM apps
WHERE delisted_at IS NULL
ORDER BY last_checked_at NULLS FIRST, appid
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


def stamp(cur, ids):
    cur.execute(
        "UPDATE apps SET last_checked_at = now() WHERE appid = ANY(%s)",
        (ids,),
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
        no_response = 0
        same = 0
        for appid in ids:
            price = parse_price(raw.get(str(appid)))
            if price is None:
                no_response += 1
                continue
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
        stamp(cur, ids)
    conn.commit()
    return {
        "apps": len(ids),
        "new": new,
        "updated": updated,
        "same": same,
        "no_response": no_response,
    }


def run(once=False):
    log = setup("sweep")
    sleep_s = 60.0 / config.RATE_PER_MIN
    checks = 0
    new_total = 0
    updated_total = 0
    same_total = 0
    no_response_total = 0
    http_429 = 0
    errors = 0
    streak = 0
    batches = 0

    log.info(
        f"sweep start batch={config.BATCH_SIZE} rate={config.RATE_PER_MIN}/min "
        f"sleep={sleep_s:.1f}s cc={config.COUNTRY}"
    )

    while True:
        with db.connect() as conn:
            with conn.cursor() as cur:
                ids = claim(cur, config.BATCH_SIZE)
            if not ids:
                log.info("no apps to check; sleeping")
                time.sleep(sleep_s)
                if once:
                    return
                continue

            try:
                stats = process_batch(conn, ids)
            except (OSError, ValueError) as e:
                if isinstance(e, urllib.error.HTTPError) and e.code == 429:
                    http_429 += 1
                    wait = retry_after(e) or sleep_s * 5
                    log.warning(f"429 backoff {wait:.0f}s ({http_429} so far)")
                else:
                    errors += 1
                    streak += 1
                    wait = sleep_s * 2 ** min(streak, 4)
                    log.warning(f"batch failed, {wait:.0f}s: {e}")
                time.sleep(wait)
                if once:
                    return
                continue

        streak = 0
        checks += stats["apps"]
        new_total += stats["new"]
        updated_total += stats["updated"]
        same_total += stats["same"]
        no_response_total += stats["no_response"]
        batches += 1
        log.info(
            f"batch={batches} apps={stats['apps']} "
            f"new={stats['new']} updated={stats['updated']} "
            f"same={stats['same']} no_response={stats['no_response']} "
            f"(sum={stats['new'] + stats['updated'] + stats['same'] + stats['no_response']}) "
            f"429s={http_429}"
        )

        if once:
            log.info(
                f"done new={new_total} updated={updated_total} "
                f"same={same_total} no_response={no_response_total} "
                f"(sum={new_total + updated_total + same_total + no_response_total} "
                f"of {checks})"
            )
            return

        if batches % 10 == 0:
            log.info(
                f"summary checks={checks} new={new_total} updated={updated_total} "
                f"same={same_total} no_response={no_response_total} "
                f"429s={http_429} errors={errors}"
            )

        time.sleep(sleep_s)


def main():
    once = "--once" in sys.argv
    run(once=once)


if __name__ == "__main__":
    main()
