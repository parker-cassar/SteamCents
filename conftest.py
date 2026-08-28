import os

import psycopg
import pytest

from steamprice import config, db

ADMIN_URL = os.environ.get(
    "TEST_ADMIN_URL", "postgresql://steamcents:steamcents@localhost:5432/postgres"
)
TEST_DB = os.environ.get("TEST_DB", "steamcents_test")

TABLES = "price_observations, apps, sweep_runs, catalog_runs"


@pytest.fixture(scope="session")
def database():
    # a throwaway database so a test run can never touch the real collection
    with psycopg.connect(ADMIN_URL, autocommit=True) as c, c.cursor() as cur:
        cur.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
        cur.execute(f'CREATE DATABASE "{TEST_DB}"')

    was = config.DATABASE_URL
    config.DATABASE_URL = ADMIN_URL.rsplit("/", 1)[0] + "/" + TEST_DB
    db.migrate()
    yield config.DATABASE_URL
    config.DATABASE_URL = was


@pytest.fixture
def conn(database):
    with db.connect() as c:
        with c.cursor() as cur:
            cur.execute(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")
        c.commit()
        yield c


@pytest.fixture
def apps(conn):
    def add(*appids):
        with conn.cursor() as cur:
            for appid in appids:
                cur.execute(
                    "INSERT INTO apps (appid, name) VALUES (%s, %s)",
                    (appid, f"app {appid}"),
                )
        conn.commit()
        return list(appids)

    return add
