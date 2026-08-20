import json
import os
import urllib.parse
import urllib.request

try:
    for line in open(".env"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))
except FileNotFoundError:
    pass


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "steamcents/0"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


print(json.dumps(get(
    "https://store.steampowered.com/api/appdetails?appids=413150&cc=us&filters=price_overview"
), indent=2))

key = os.environ.get("STEAM_WEB_API_KEY")
if not key:
    raise SystemExit("set STEAM_WEB_API_KEY (https://steamcommunity.com/dev/apikey)")

apps = []
last = 0
while True:
    q = urllib.parse.urlencode({
        "key": key,
        "include_games": 1,
        "include_dlc": 1,
        "include_software": 1,
        "include_videos": 1,
        "include_hardware": 1,
        "max_results": 50000,
        "last_appid": last,
    })
    resp = get("https://api.steampowered.com/IStoreService/GetAppList/v1/?" + q)["response"]
    batch = resp.get("apps") or []
    apps.extend(batch)
    if not resp.get("have_more_results") or not batch:
        break
    last = resp.get("last_appid") or batch[-1]["appid"]

print(len(apps), "apps")
print(json.dumps(apps[:5], indent=2))
