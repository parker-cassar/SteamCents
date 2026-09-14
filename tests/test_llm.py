import json

from steamprice import config
from steamprice.llm import complete_json


def test_mock_llm_returns_structured_brief(monkeypatch):
    monkeypatch.setattr(config, "BRIEF_LLM", "mock")
    facts = {
        "period": {"changes": 3, "checks": 10},
        "catalog": {"coverage_pct": 99.0, "live": 5, "checked": 5},
        "top_drops": [{
            "name": "A", "drop_pct": 40,
            "prev_final_cents": 1000, "final_cents": 600,
        }],
    }
    out = complete_json("sys", json.dumps(facts))
    assert out["headline"]
    assert out["summary"]
    assert out["highlights"]
    assert out["highlights"][0]["source"] == "top_drops[0]"
