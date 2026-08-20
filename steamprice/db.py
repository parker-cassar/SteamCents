import pathlib

import psycopg

from steamprice import config

ROOT = pathlib.Path(__file__).resolve().parents[1]


def connect():
    return psycopg.connect(config.DATABASE_URL)


def migrate(conn=None):
    sql = (ROOT / "migrations" / "001_init.sql").read_text()
    own = conn is None
    if own:
        conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        if own:
            conn.close()
