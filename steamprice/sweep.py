import sys
import time
import urllib.error

from steamprice import config, db
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
        deltas = 0
        priced = 0
        for appid in ids:
            price = parse_price(raw.get(str(appid)))
            if price is None:
                continue
            priced += 1
            if not changed(prev.get(appid), price):
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
            deltas += 1
        stamp(cur, ids)
    conn.commit()
    return priced, deltas


def run(once=False):
    sleep_s = 60.0 / config.RATE_PER_MIN
    checks = 0
    deltas_total = 0
    http_429 = 0
    batches = 0

    print(
        f"sweep batch={config.BATCH_SIZE} rate={config.RATE_PER_MIN}/min "
        f"sleep={sleep_s:.1f}s cc={config.COUNTRY}"
    )

    while True:
        with db.connect() as conn:
            with conn.cursor() as cur:
                ids = claim(cur, config.BATCH_SIZE)
            if not ids:
                print("no apps to check; sleeping")
                time.sleep(sleep_s)
                if once:
                    return
                continue

            try:
                priced, deltas = process_batch(conn, ids)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    http_429 += 1
                    print(f"429 backoff ({http_429} so far)")
                    time.sleep(sleep_s * 5)
                    if once:
                        return
                    continue
                raise

        checks += len(ids)
        deltas_total += deltas
        batches += 1
        print(
            f"batch={batches} apps={len(ids)} priced={priced} "
            f"deltas={deltas} checks={checks} deltas_total={deltas_total} 429s={http_429}"
        )

        if once:
            return

        if batches % 10 == 0:
            print(
                f"summary checks={checks} deltas={deltas_total} "
                f"429s={http_429} rate={config.RATE_PER_MIN}/min"
            )

        time.sleep(sleep_s)


def main():
    once = "--once" in sys.argv
    run(once=once)


if __name__ == "__main__":
    main()
