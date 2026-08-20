import json
import urllib.parse
import urllib.request

from steamprice import config


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


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
