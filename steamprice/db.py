import pathlib

import psycopg

from steamprice import config

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"

LEDGER = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  filename   text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def connect():
    return psycopg.connect(config.DATABASE_URL)


def migrate(conn=None):
    own = conn is None
    if own:
        conn = connect()
    applied = []
    try:
        with conn.cursor() as cur:
            cur.execute(LEDGER)
            conn.commit()
            cur.execute("SELECT filename FROM schema_migrations")
            done = {r[0] for r in cur.fetchall()}

            for path in sorted(MIGRATIONS.glob("*.sql")):
                if path.name in done:
                    continue
                cur.execute(path.read_text())
                cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
                # commit per file so a bad one later does not undo the good ones
                conn.commit()
                applied.append(path.name)
    finally:
        if own:
            conn.close()
    return applied
