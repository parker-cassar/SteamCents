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
