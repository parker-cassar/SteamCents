import json
import re
import sys

from psycopg.types.json import Json

from steamprice import config, db
from steamprice.facts import build_facts
from steamprice.llm import complete_json
from steamprice.log import setup

PROMPT_VERSION = config.BRIEF_PROMPT_VERSION

SYSTEM = """You write a short weekly Steam price brief for a dashboard.
Use ONLY the JSON facts the user provides. Do not invent apps, prices, or counts.
Every highlight must set "source" to a dotted path into that JSON
(e.g. "period.changes", "catalog.coverage_pct", "top_drops[0]").
Reply with a single JSON object, no markdown, matching:
{
  "headline": string,
  "summary": string,
  "highlights": [{"claim": string, "source": string}],
  "watchouts": [string],
  "coverage_note": string
}
Keep headline under 80 chars. Summary under 280 chars. At most 5 highlights.
If top_drops is empty, say so in summary and use period/catalog sources only.
"""


class BriefInvalid(ValueError):
    pass


def _resolve_source(facts, source):
    # period.changes or top_drops[0] or top_drops[0].drop_pct
    if not source or not isinstance(source, str):
        return None
    cur = facts
    for part in re.split(r"\.", source):
        m = re.fullmatch(r"(\w+)(?:\[(\d+)\])?", part)
        if not m:
            return None
        key, idx = m.group(1), m.group(2)
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
        if idx is not None:
            i = int(idx)
            if not isinstance(cur, list) or i < 0 or i >= len(cur):
                return None
            cur = cur[i]
    return cur


def validate_brief(brief, facts):
    if not isinstance(brief, dict):
        raise BriefInvalid("brief must be an object")
    for key in ("headline", "summary", "highlights", "watchouts", "coverage_note"):
        if key not in brief:
            raise BriefInvalid(f"missing {key}")
    if not isinstance(brief["headline"], str) or not brief["headline"].strip():
        raise BriefInvalid("headline must be a non-empty string")
    if not isinstance(brief["summary"], str) or not brief["summary"].strip():
        raise BriefInvalid("summary must be a non-empty string")
    if not isinstance(brief["coverage_note"], str):
        raise BriefInvalid("coverage_note must be a string")
    if not isinstance(brief["watchouts"], list) or not all(
        isinstance(w, str) for w in brief["watchouts"]
    ):
        raise BriefInvalid("watchouts must be a list of strings")
    if not isinstance(brief["highlights"], list) or len(brief["highlights"]) > 5:
        raise BriefInvalid("highlights must be a list of at most 5")
    for i, h in enumerate(brief["highlights"]):
        if not isinstance(h, dict):
            raise BriefInvalid(f"highlights[{i}] must be an object")
        if not isinstance(h.get("claim"), str) or not h["claim"].strip():
            raise BriefInvalid(f"highlights[{i}].claim required")
        src = h.get("source")
        if _resolve_source(facts, src) is None:
            raise BriefInvalid(f"highlights[{i}].source not in facts: {src!r}")
    return {
        "headline": brief["headline"].strip(),
        "summary": brief["summary"].strip(),
        "highlights": [
            {"claim": h["claim"].strip(), "source": h["source"]}
            for h in brief["highlights"]
        ],
        "watchouts": [w.strip() for w in brief["watchouts"] if w.strip()],
        "coverage_note": brief["coverage_note"].strip(),
    }


def generate(facts, model=None):
    raw = complete_json(SYSTEM, json.dumps(facts, default=str), model=model)
    return validate_brief(raw, facts)


def existing(cur, period_start, period_end, prompt_version=PROMPT_VERSION):
    cur.execute("""
        SELECT id FROM briefs
        WHERE period_start = %s AND period_end = %s AND prompt_version = %s
    """, (period_start, period_end, prompt_version))
    row = cur.fetchone()
    return row[0] if row else None


def store(cur, facts, brief, model, prompt_version=PROMPT_VERSION, force=False):
    period_start = facts["period_start"]
    period_end = facts["period_end"]
    found = existing(cur, period_start, period_end, prompt_version)
    if found and not force:
        return found, False
    if found and force:
        cur.execute("DELETE FROM briefs WHERE id = %s", (found,))
    cur.execute("""
        INSERT INTO briefs (
          period_start, period_end, facts_json, brief_json, model, prompt_version
        ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        period_start, period_end,
        Json(facts), Json(brief),
        model, prompt_version,
    ))
    return cur.fetchone()[0], True


def run(days=None, force=False, dry_run=False):
    log = setup("brief")
    days = days if days is not None else config.BRIEF_DAYS
    model = "mock" if config.BRIEF_LLM == "mock" else config.BRIEF_MODEL

    with db.connect() as conn, conn.cursor() as cur:
        facts = build_facts(cur, days=days)
        if dry_run:
            print(json.dumps(facts, indent=2, default=str))
            return None

        found = existing(cur, facts["period_start"], facts["period_end"])
        if found and not force:
            log.info(f"brief already exists id={found}; pass --force to replace")
            print(f"exists id={found}")
            return found

        brief = generate(facts, model=None if config.BRIEF_LLM == "mock" else model)
        brief_id, wrote = store(cur, facts, brief, model, force=force)
        conn.commit()
        log.info(f"brief id={brief_id} wrote={wrote} model={model}")
        print(f"brief id={brief_id}")
        return brief_id


def status():
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, period_start, period_end, model, prompt_version, created_at
            FROM briefs ORDER BY created_at DESC LIMIT 5
        """)
        rows = cur.fetchall()
    if not rows:
        print("no briefs yet")
        return
    for r in rows:
        print(
            f"id={r[0]} {r[1]}..{r[2]} model={r[3]} prompt={r[4]} "
            f"at={r[5]:%Y-%m-%d %H:%M}"
        )


def main():
    args = sys.argv[1:]
    if "--status" in args:
        status()
        return
    force = "--force" in args
    dry_run = "--dry-run" in args
    days = config.BRIEF_DAYS
    if "--days" in args:
        i = args.index("--days")
        days = int(args[i + 1])
    run(days=days, force=force, dry_run=dry_run)


if __name__ == "__main__":
    main()
