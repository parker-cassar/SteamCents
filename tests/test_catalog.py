import pytest

from steamprice import catalog, config


@pytest.fixture
def steam(monkeypatch):
    listing = []
    monkeypatch.setattr(catalog, "fetch_applist", lambda key: listing)
    monkeypatch.setattr(config, "STEAM_WEB_API_KEY", "test-key")
    return listing


def listing(*appids):
    return [{"appid": i, "name": f"app {i}"} for i in appids]


def counts(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FILTER (WHERE delisted_at IS NULL), count(*) FROM apps")
        return cur.fetchone()


def last_run(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT exit_reason, remote_apps, live, newly_delisted, note "
            "FROM catalog_runs ORDER BY id DESC LIMIT 1"
        )
        return cur.fetchone()


def test_sync_adds_and_delists(conn, apps, steam):
    apps(*range(1, 21))
    steam[:] = listing(*range(1, 20))  # 19 of the 20 come back, plus one new
    steam.extend(listing(99))

    catalog.sync()

    live, total = counts(conn)
    assert (live, total) == (20, 21)
    reason, remote, live_recorded, delisted, _ = last_run(conn)
    assert reason == "ok"
    assert (remote, live_recorded, delisted) == (20, 20, 1)


def test_guard_refuses_a_truncated_response(conn, apps, steam):
    apps(*range(1, 101))
    steam[:] = listing(1, 2, 3)  # steam only coughed up 3 of 100

    with pytest.raises(SystemExit):
        catalog.sync()

    assert counts(conn) == (100, 100)
    reason, remote, _, delisted, note = last_run(conn)
    assert reason == "guard"
    assert (remote, delisted) == (3, 0)
    assert "under 90%" in note


def test_guard_allows_a_small_dip(conn, apps, steam):
    apps(*range(1, 101))
    steam[:] = listing(*range(1, 96))  # 95 of 100 is above the line

    catalog.sync()

    live, _ = counts(conn)
    assert live == 95
    assert last_run(conn)[0] == "ok"


def test_guard_does_not_block_the_first_ever_sync(conn, steam):
    steam[:] = listing(1, 2, 3)

    catalog.sync()

    assert counts(conn) == (3, 3)
    assert last_run(conn)[0] == "ok"


def test_a_returning_app_is_undelisted(conn, apps, steam):
    apps(*range(1, 101))
    with conn.cursor() as cur:
        cur.execute("UPDATE apps SET delisted_at = now() WHERE appid = 50")
    conn.commit()

    steam[:] = listing(*range(1, 101))
    catalog.sync()

    with conn.cursor() as cur:
        cur.execute("SELECT delisted_at FROM apps WHERE appid = 50")
        assert cur.fetchone()[0] is None
