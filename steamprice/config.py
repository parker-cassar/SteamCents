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

# recheck cadence per tier, in hours. this is politeness, not budget: at 10
# requests a minute times 100 ids the whole catalog fits in about four hours.
# retune once there is a week of real change data to look at.
TIER_HOURS = {0: 6, 1: 24, 2: 24 * 7}
CHANGED_RECENTLY_DAYS = 14

API_ORIGINS = [
    o.strip() for o in os.environ.get(
        "API_ORIGINS",
        "https://steamcents.com,https://www.steamcents.com,http://localhost:3000",
    ).split(",") if o.strip()
]
