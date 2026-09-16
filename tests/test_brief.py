import json

import pytest

from steamprice import brief, config
from steamprice.brief import BriefInvalid, validate_brief


def seed_drop(conn, appid, name, prev, final):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO apps (appid, name) VALUES (%s, %s)", (appid, name))
        cur.execute("""
            INSERT INTO price_observations
              (appid, country_code, observed_at, currency, initial_cents,
               final_cents, discount_pct)
            VALUES
              (%s, %s, now() - interval '2 days', 'USD', %s, %s, 0),
              (%s, %s, now() - interval '1 day', 'USD', %s, %s, 0)
        """, (appid, config.COUNTRY, prev, prev, appid, config.COUNTRY, final, final))
        cur.execute("""
            INSERT INTO sweep_runs (apps_checked, changes, http_429s, errors)
            VALUES (100, 1, 0, 0)
        """)
    conn.commit()


def test_validate_rejects_bad_source():
    facts_payload = {
        "period": {"changes": 3},
        "catalog": {"coverage_pct": 100},
        "top_drops": [],
    }
    with pytest.raises(BriefInvalid, match="source"):
        validate_brief({
            "headline": "x",
            "summary": "y",
            "highlights": [{"claim": "z", "source": "nope.missing"}],
            "watchouts": [],
            "coverage_note": "ok",
        }, facts_payload)


def test_validate_accepts_good_source():
    facts_payload = {
        "period": {"changes": 3},
        "catalog": {"coverage_pct": 100.0},
        "top_drops": [{"name": "A", "drop_pct": 50}],
    }
    out = validate_brief({
        "headline": "Week",
        "summary": "Stuff moved",
        "highlights": [
            {"claim": "3 changes", "source": "period.changes"},
            {"claim": "A fell", "source": "top_drops[0]"},
        ],
        "watchouts": [],
        "coverage_note": "full",
    }, facts_payload)
    assert out["headline"] == "Week"
    assert len(out["highlights"]) == 2


def test_run_stores_brief_with_mock_llm(conn, monkeypatch):
    monkeypatch.setattr(config, "BRIEF_LLM", "mock")
    seed_drop(conn, 10, "Fine Game", 2000, 1000)

    brief_id = brief.run(days=7, force=False)
    assert brief_id is not None

    with conn.cursor() as cur:
        cur.execute(
            "SELECT brief_json, model, prompt_version FROM briefs WHERE id = %s",
            (brief_id,),
        )
        row = cur.fetchone()
    body = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    assert body["headline"]
    assert row[1] == "mock"

    same = brief.run(days=7, force=False)
    assert same == brief_id

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM briefs")
        assert cur.fetchone()[0] == 1
