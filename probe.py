import json
import os
import pathlib
import urllib.error
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

FIXTURES = pathlib.Path("tests/fixtures")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "steamcents/0"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def appdetails(ids):
    q = urllib.parse.urlencode({
        "appids": ",".join(str(i) for i in ids),
        "cc": "us",
        "filters": "price_overview",
    })
    return get("https://store.steampowered.com/api/appdetails?" + q)


def applist_page(key, max_results=100, last_appid=0):
    q = urllib.parse.urlencode({
        "key": key,
        "include_games": 1,
        "include_dlc": 1,
        "include_software": 1,
        "include_videos": 1,
        "include_hardware": 1,
        "max_results": max_results,
        "last_appid": last_appid,
    })
    resp = get("https://api.steampowered.com/IStoreService/GetAppList/v1/?" + q)["response"]
    return resp.get("apps") or []


def count_batch(data):
    ok = 0
    priced = 0
    empty = 0
    for v in data.values():
        if not isinstance(v, dict):
            continue
        if v.get("success"):
            ok += 1
        d = v.get("data")
        if isinstance(d, dict) and "price_overview" in d:
            priced += 1
        elif d == []:
            empty += 1
    return {
        "returned": len(data),
        "ok": ok,
        "priced": priced,
        "empty_data": empty,
    }


def summarize(n, data):
    c = count_batch(data)
    print(f"n={n} returned={c['returned']} ok={c['ok']} priced={c['priced']} empty_data={c['empty_data']}")
    return c


key = os.environ.get("STEAM_WEB_API_KEY")
if not key:
    raise SystemExit("set STEAM_WEB_API_KEY (https://steamcommunity.com/dev/apikey)")

apps = applist_page(key, max_results=100)
print(f"{len(apps)} apps from first GetAppList page")

ids = [a["appid"] for a in apps]
for n in (5, 10, 20, 50, 100):
    try:
        summarize(n, appdetails(ids[:n]))
    except urllib.error.HTTPError as e:
        print(f"n={n} http {e.code}")


# already done
def save_batch_fixture(ids):
    batch = appdetails(ids)
    counts = count_batch(batch)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "appdetails_batch_100.json").write_text(json.dumps(batch, indent=2) + "\n")
    (FIXTURES / "appdetails_batch_100.expected.json").write_text(json.dumps({
        "ids": ids,
        **counts,
    }, indent=2) + "\n")
    print(f"wrote {FIXTURES / 'appdetails_batch_100.json'}")
    print(f"wrote {FIXTURES / 'appdetails_batch_100.expected.json'} {counts}")
