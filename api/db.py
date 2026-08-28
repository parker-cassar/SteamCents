from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from steamprice import config

_pool = None


def pool():
    # built on first use, not at import, so the tests can point config at a
    # throwaway database before anything connects
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            config.DATABASE_URL, min_size=1, max_size=4, open=True, kwargs={"autocommit": True}
        )
    return _pool


def reset():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def rows(sql, params=()):
    with pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def one(sql, params=()):
    found = rows(sql, params)
    return found[0] if found else None
