import json
import urllib.request

url = "https://store.steampowered.com/api/appdetails?appids=413150&cc=us&filters=price_overview"
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as r:
    print(json.dumps(json.load(r), indent=2))
