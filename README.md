# steamcents

Tracks US Steam prices across the whole catalog. Not a deal site. Just a collector that remembers what things cost and when they moved.

Steam's storefront is slow and undocumented if you poke it wrong, so this stays polite: batch `appdetails` (100 ids per request), sleep between calls, back off on 429s. Postgres holds the catalog and a delta-only price history. New / never-checked apps get checked first.

## Quick start

```bash
cp .env.example .env   # add STEAM_WEB_API_KEY
docker compose up -d
pip install -r requirements.txt

python3 -m steamprice.catalog migrate
python3 -m steamprice.catalog
python3 -m steamprice.sweep --once   # or drop --once to leave it running
```

Get a free Web API key at https://steamcommunity.com/dev/apikey

## Layout

```
steamprice/     catalog + sweep
migrations/     apps + price_observations
tests/          fixtures + parse tests
probe.py        early Steam API experiments
```

## License

Nothing fancy yet. Ask if you want to use it.
