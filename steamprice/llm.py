import json
import re
import urllib.error
import urllib.parse
import urllib.request

from steamprice import config

TIMEOUT = 60


def _strip_fence(text):
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
    return m.group(1).strip() if m else text


def complete_json(system, user, model=None):
    """Return a parsed JSON object from the model. Raises on bad transport/JSON."""
    if config.BRIEF_LLM == "mock":
        return _mock_brief(user)

    model = model or config.BRIEF_MODEL
    key = config.GEMINI_API_KEY
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    q = urllib.parse.urlencode({"key": key})
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model, safe='')}:generateContent?{q}"
    )
    body = json.dumps({
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }).encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "content-type": "application/json",
            "user-agent": config.USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"gemini HTTP {e.code}: {detail}") from e

    parts = []
    for cand in payload.get("candidates") or []:
        content = cand.get("content") or {}
        for part in content.get("parts") or []:
            if "text" in part:
                parts.append(part["text"])
    raw = _strip_fence("".join(parts))
    if not raw:
        raise RuntimeError(f"gemini returned empty text: {payload!r}"[:300])
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"model returned non-JSON: {raw[:200]!r}") from e


def _mock_brief(user):
    # tests pass the facts JSON as the user message
    try:
        facts = json.loads(user)
    except json.JSONDecodeError:
        facts = {}
    period = facts.get("period") or {}
    drops = facts.get("top_drops") or []
    highlights = []
    if drops:
        d = drops[0]
        highlights.append({
            "claim": (
                f"{d.get('name')} dropped {d.get('drop_pct')}% "
                f"({d.get('prev_final_cents')} -> {d.get('final_cents')} cents)"
            ),
            "source": "top_drops[0]",
        })
    highlights.append({
        "claim": f"{period.get('changes', 0)} price changes across {period.get('checks', 0)} checks",
        "source": "period.changes",
    })
    catalog = facts.get("catalog") or {}
    return {
        "headline": "Weekly Steam price brief",
        "summary": (
            f"Coverage {catalog.get('coverage_pct')}% over "
            f"{catalog.get('live')} live apps."
        ),
        "highlights": highlights,
        "watchouts": [],
        "coverage_note": f"{catalog.get('checked')} of {catalog.get('live')} live apps checked.",
    }
