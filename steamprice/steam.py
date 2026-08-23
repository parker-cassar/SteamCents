import json
import time
import urllib.error
import urllib.parse
import urllib.request

from steamprice import config

TIMEOUT = 30
RETRY_CODES = {408, 500, 502, 503, 504}


def get(url, tries=4):
    delay = 2.0
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # 429 is the caller's problem, it needs to slow the whole sweep down
            if e.code not in RETRY_CODES:
                raise
            err = e
        except (OSError, ValueError) as e:
            # dropped connections, timeouts, and the html error pages steam
            # sometimes serves instead of json
            err = e
        if attempt == tries - 1:
            raise err
        time.sleep(delay)
        delay *= 2


def fetch_applist(key):
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
    return apps


def fetch_appdetails(ids, cc=None):
    cc = cc or config.COUNTRY
    q = urllib.parse.urlencode({
        "appids": ",".join(str(i) for i in ids),
        "cc": cc,
        "filters": "price_overview",
    })
    return get("https://store.steampowered.com/api/appdetails?" + q)


def parse_price(entry):
    if not isinstance(entry, dict) or not entry.get("success"):
        return None
    data = entry.get("data")
    if not isinstance(data, dict):
        return None
    po = data.get("price_overview")
    if not isinstance(po, dict):
        return None
    return {
        "currency": po["currency"],
        "initial_cents": int(po["initial"]),
        "final_cents": int(po["final"]),
        "discount_pct": int(po["discount_percent"]),
    }
