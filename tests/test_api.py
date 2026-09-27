import pytest
from fastapi.testclient import TestClient

from api import db as apidb
from api.main import app
from steamprice import config, db, sweep


@pytest.fixture
def client(conn, monkeypatch):
    # the pool is lazy, so dropping it here makes it rebuild against the test db
    apidb.reset()
    with TestClient(app) as c:
        yield c
    apidb.reset()


def seed(conn, appid, name, prices):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO apps (appid, name) VALUES (%s, %s)", (appid, name))
        for n, cents in enumerate(prices):
            cur.execute("""
                INSERT INTO price_observations
                  (appid, country_code, observed_at, currency, initial_cents,
                   final_cents, discount_pct)
                VALUES (%s, %s, now() - make_interval(hours => %s), 'USD', %s, %s, 0)
            """, (appid, config.COUNTRY, len(prices) - n, cents, cents))
    conn.commit()


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_stats_counts_what_it_says(client, conn):
    seed(conn, 10, "Priced", [1999, 999])
    seed(conn, 20, "Free", [])
    with conn.cursor() as cur:
        cur.execute("UPDATE apps SET last_checked_at = now(), no_price_seen_at = now() WHERE appid = 20")
        cur.execute("UPDATE apps SET last_checked_at = now() WHERE appid = 10")
    conn.commit()

    s = client.get("/stats").json()
    assert s["catalog"]["apps"] == 2
    assert s["catalog"]["unpriced"] == 1
    assert s["prices"]["observations"] == 2
    assert s["prices"]["apps_with_price"] == 1
    assert s["coverage_pct"] == 100.0


def test_coverage_never_exceeds_100(client, conn):
    seed(conn, 10, "Live", [500])
    seed(conn, 20, "Gone", [500])
    with conn.cursor() as cur:
        # a delisted app that was checked must not count against a live denominator
        cur.execute("UPDATE apps SET last_checked_at = now()")
        cur.execute("UPDATE apps SET delisted_at = now() WHERE appid = 20")
    conn.commit()

    assert client.get("/stats").json()["coverage_pct"] == 100.0


def test_history_is_in_order(client, conn):
    seed(conn, 10, "Thing", [1999, 1499, 999])
    body = client.get("/apps/10/history").json()
    assert [o["final_cents"] for o in body["observations"]] == [1999, 1499, 999]


def test_history_paginates(client, conn):
    seed(conn, 10, "Thing", [1999, 1499, 999])
    page = client.get("/apps/10/history?limit=2&offset=1").json()
    assert [o["final_cents"] for o in page["observations"]] == [1499, 999]


def test_unknown_app_is_404(client):
    assert client.get("/apps/424242").status_code == 404
    assert client.get("/apps/424242/history").status_code == 404


def test_latest_price_comes_back_on_the_app(client, conn):
    seed(conn, 10, "Thing", [1999, 999])
    assert client.get("/apps/10").json()["final_cents"] == 999


def test_first_observation_is_not_a_change(client, conn):
    seed(conn, 10, "Thing", [1999])
    assert client.get("/changes").json()["changes"] == []

    seed(conn, 20, "Other", [1999, 999])
    changes = client.get("/changes").json()["changes"]
    assert len(changes) == 1
    assert (changes[0]["prev_final_cents"], changes[0]["final_cents"]) == (1999, 999)


def test_drops_exclude_rises(client, conn):
    seed(conn, 10, "Fell", [2000, 1000])
    seed(conn, 20, "Rose", [1000, 2000])

    drops = client.get("/drops?days=30").json()["drops"]
    assert [d["appid"] for d in drops] == [10]
    assert drops[0]["drop_cents"] == 1000
    assert float(drops[0]["drop_pct"]) == 50.0


def test_drops_balance_savings_and_percentage_rankings(client, conn):
    seed(conn, 10, "Big Savings", [10000, 5000])
    seed(conn, 20, "Big Percentage", [1000, 10])
    seed(conn, 30, "Second Savings", [8000, 4000])
    seed(conn, 40, "Second Percentage", [1000, 20])

    drops = client.get("/drops?days=30&limit=4").json()["drops"]
    assert [d["appid"] for d in drops] == [10, 20, 30, 40]


def test_daily_series_splits_drops_and_rises(client, conn):
    seed(conn, 10, "Fell", [2000, 1000])
    seed(conn, 20, "Rose", [1000, 2000])

    series = client.get("/changes/daily?days=7").json()["series"]
    assert sum(d["drops"] for d in series) == 1
    assert sum(d["rises"] for d in series) == 1


def test_changes_since_filters(client, conn):
    seed(conn, 10, "Thing", [1999, 999])
    assert client.get("/changes?since=2099-01-01T00:00:00Z").json()["changes"] == []
    assert len(client.get("/changes?since=2000-01-01T00:00:00Z").json()["changes"]) == 1


def test_limits_are_capped(client):
    assert client.get("/drops?limit=100000").status_code == 422
    assert client.get("/changes?limit=0").status_code == 422
    assert client.get("/apps/10/history?offset=-1").status_code == 422


def test_blocked_titles_are_hidden(client, conn):
    seed(conn, 10, "Fine Game", [2000, 1000])
    seed(conn, 20, "Hentai Discount", [2000, 1000])
    seed(conn, 40, "Desktop Sex Doll", [2000, 1000])

    drops = client.get("/drops?days=30").json()["drops"]
    assert [d["appid"] for d in drops] == [10]

    assert client.get("/apps/20").status_code == 404
    assert client.get("/apps/20/history").status_code == 404
    assert client.get("/apps/40").status_code == 404

    seed(conn, 30, "Other", [1999, 999])
    changes = client.get("/changes").json()["changes"]
    assert {c["appid"] for c in changes} == {10, 30}


def test_briefs_latest_404_when_empty(client):
    assert client.get("/briefs/latest").status_code == 404


def test_briefs_latest_returns_stored_json(client, conn):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO briefs (
              period_start, period_end, facts_json, brief_json, model, prompt_version
            ) VALUES (
              current_date - 7, current_date,
              '{}'::jsonb,
              '{"headline":"hi","summary":"there","highlights":[],"watchouts":[],"coverage_note":"ok"}'::jsonb,
              'mock', 'v1'
            )
        """)
    conn.commit()

    body = client.get("/briefs/latest").json()
    assert body["brief"]["headline"] == "hi"
    assert body["model"] == "mock"
    assert body["prompt_version"] == "v1"


def test_stats_reports_the_live_sweep(client, conn, apps, monkeypatch):
    ids = apps(10)
    monkeypatch.setattr(sweep, "fetch_appdetails", lambda i, cc=None: {
        "10": {"success": True, "data": {"price_overview": {
            "currency": "USD", "initial": 1999, "final": 1999, "discount_percent": 0}}}
    })
    with db.connect() as c:
        run_id = sweep.start_run(c)
        sweep.process_batch(c, ids)
        sweep.beat(c, run_id, 1, 100, 0, 0, 0)

    s = client.get("/stats").json()
    assert s["sweep"]["id"] == run_id
    assert s["sweep"]["batches"] == 1
    assert s["totals"]["checks"] == 100
