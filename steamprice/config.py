import os

try:
    for line in open(".env"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))
except FileNotFoundError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://steamcents:steamcents@localhost:5432/steamcents")
STEAM_WEB_API_KEY = os.environ.get("STEAM_WEB_API_KEY")
USER_AGENT = "steamcents/0 (local v0; price history)"
COUNTRY = "us"
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "100"))
RATE_PER_MIN = float(os.environ.get("RATE_PER_MIN", "10"))
LOG_DIR = os.environ.get("LOG_DIR", "logs")

MAX_FAILURES = int(os.environ.get("MAX_FAILURES", "5"))

# recheck cadence per tier, in hours. still a guess, not fit to real change
# data (only ~3k apps have ever had a second observation and that sample is
# one lump, not a rate). picked to use under half the crawl's ~60k apps/hour
# budget at current tier sizes, leaving room for the catalog to grow.
# retune once there is a week of real change data to look at.
TIER_HOURS = {0: 2, 1: 12, 2: 24 * 3}
CHANGED_RECENTLY_DAYS = 14

API_ORIGINS = [
    o.strip() for o in os.environ.get(
        "API_ORIGINS",
        "https://steamcents.com,https://www.steamcents.com,http://localhost:3000",
    ).split(",") if o.strip()
]

# weekly brief: gemini generateContent. BRIEF_LLM=mock skips the network (tests).
BRIEF_LLM = os.environ.get("BRIEF_LLM", "gemini")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
BRIEF_MODEL = os.environ.get("BRIEF_MODEL", "gemini-2.0-flash")
BRIEF_DAYS = int(os.environ.get("BRIEF_DAYS", "7"))
BRIEF_PROMPT_VERSION = os.environ.get("BRIEF_PROMPT_VERSION", "v1")
