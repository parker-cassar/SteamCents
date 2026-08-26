import sys

from steamprice import config, db
from steamprice.log import setup
from steamprice.steam import fetch_applist

UPSERT = """
INSERT INTO apps (appid, name, last_seen_at)
VALUES (%s, %s, now())
ON CONFLICT (appid) DO UPDATE SET
  name = EXCLUDED.name,
  last_seen_at = now(),
  delisted_at = NULL
"""


class Guard(Exception):
    pass


def start_run():
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO catalog_runs DEFAULT VALUES RETURNING id")
            run_id = cur.fetchone()[0]
        conn.commit()
    return run_id


def end_run(run_id, reason, counts=None, note=None):
    c = counts or {}
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE catalog_runs
                SET ended_at = now(), exit_reason = %s, remote_apps = %s,
                    total = %s, live = %s, newly_delisted = %s, note = %s
                WHERE id = %s
            """, (
                reason, c.get("remote", 0), c.get("total", 0), c.get("live", 0),
                c.get("delisted", 0), note, run_id,
            ))
        conn.commit()


def write(rows, ids, counts):
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM apps WHERE delisted_at IS NULL")
            live_before = cur.fetchone()[0]

            if live_before and len(rows) < 0.9 * live_before:
                raise Guard(
                    f"steam returned {len(rows)}, live db has {live_before} (under 90%)"
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
            counts["delisted"] = cur.rowcount

            cur.execute("SELECT count(*) FROM apps WHERE delisted_at IS NULL")
            counts["live"] = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM apps")
            counts["total"] = cur.fetchone()[0]

        conn.commit()


def sync():
    log = setup("catalog")
    key = config.STEAM_WEB_API_KEY
    if not key:
        raise SystemExit("set STEAM_WEB_API_KEY in .env")

    run_id = start_run()
    counts = {}
    reason = "crash"
    note = None
    try:
        log.info("fetching GetAppList...")
        remote = fetch_applist(key)
        counts["remote"] = len(remote)
        log.info(f"got {len(remote)} apps from steam")

        by_id = {}
        for a in remote:
            appid = a["appid"]
            by_id[appid] = a.get("name") or f"appid:{appid}"

        write(list(by_id.items()), list(by_id), counts)
        reason = "ok"
        log.info(
            f"apps total={counts['total']} live={counts['live']} "
            f"newly_delisted={counts['delisted']}"
        )
    except Guard as e:
        reason = "guard"
        note = str(e)
        log.error(f"catalog guard: {e}. not writing.")
        raise SystemExit(1)
    except Exception as e:
        reason = "error"
        note = f"{type(e).__name__}: {e}"
        log.exception("catalog sync failed")
        raise
    finally:
        end_run(run_id, reason, counts, note)


def status():
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, started_at, exit_reason, remote_apps, total, live,
                   newly_delisted, note, now() - started_at
            FROM catalog_runs ORDER BY id DESC LIMIT 5
        """)
        for r in cur.fetchall():
            line = (
                f"run={r[0]} {r[2] or 'running'} started={r[1]:%Y-%m-%d %H:%M} "
                f"remote={r[3]} total={r[4]} live={r[5]} delisted={r[6]} "
                f"({str(r[8]).split('.')[0]} ago)"
            )
            print(line + (f" note={r[7]}" if r[7] else ""))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        applied = db.migrate()
        print("applied " + ", ".join(applied) if applied else "already up to date")
        return
    if "--status" in sys.argv:
        status()
        return
    sync()


if __name__ == "__main__":
    main()
