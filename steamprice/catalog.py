import sys

from steamprice import config, db
from steamprice.steam import fetch_applist

UPSERT = """
INSERT INTO apps (appid, name, last_seen_at)
VALUES (%s, %s, now())
ON CONFLICT (appid) DO UPDATE SET
  name = EXCLUDED.name,
  last_seen_at = now(),
  delisted_at = NULL
"""


def sync():
    key = config.STEAM_WEB_API_KEY
    if not key:
        raise SystemExit("set STEAM_WEB_API_KEY in .env")

    print("fetching GetAppList...")
    remote = fetch_applist(key)
    print(f"got {len(remote)} apps from steam")

    by_id = {}
    for a in remote:
        appid = a["appid"]
        by_id[appid] = a.get("name") or f"appid:{appid}"
    rows = list(by_id.items())
    ids = list(by_id)

    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM apps WHERE delisted_at IS NULL")
            live_before = cur.fetchone()[0]

            if live_before and len(rows) < 0.9 * live_before:
                raise SystemExit(
                    f"catalog guard: steam returned {len(rows)}, live db has {live_before} "
                    f"(under 90%). not writing."
                )

            cur.execute("CREATE TEMP TABLE catalog_seen (appid integer PRIMARY KEY) ON COMMIT DROP")
            cur.executemany(
                "INSERT INTO catalog_seen (appid) VALUES (%s)",
                [(i,) for i in ids],
            )

            cur.executemany(UPSERT, rows)

            cur.execute("""
                UPDATE apps
                SET delisted_at = now()
                WHERE delisted_at IS NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM catalog_seen s WHERE s.appid = apps.appid
                  )
            """)
            delisted = cur.rowcount

            cur.execute("SELECT count(*) FROM apps WHERE delisted_at IS NULL")
            live = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM apps")
            total = cur.fetchone()[0]

        conn.commit()

    print(f"apps total={total} live={live} newly_delisted={delisted}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        db.migrate()
        print("migrated")
        return
    sync()


if __name__ == "__main__":
    main()
