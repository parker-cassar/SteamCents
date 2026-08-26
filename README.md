# steamcents

Tracks US Steam prices across the whole catalog. Not a deal site. Just a collector that remembers what things cost and when they moved.

Steam's storefront is slow and undocumented if you poke it wrong, so this stays polite: batch `appdetails` (100 ids per request), sleep between calls, back off on 429s. Postgres holds the catalog and a delta-only price history. New / never-checked apps get checked first.

Apps are rechecked on a tier: 6 hours if the price moved in the last two weeks,
24 hours if it is priced and quiet, 7 days if Steam reports no price at all
(free games, videos, hardware, most DLC). Cadences live in `steamprice/config.py`.
About a third of the catalog has no price, and Steam says so with
`{"success": true, "data": []}`, which is a real answer and not a failed request.

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

## Leaving it running (macOS)

```bash
sed "s|__REPO__|$PWD|g" ops/com.steamcents.sweep.plist.template \
  > ~/Library/LaunchAgents/com.steamcents.sweep.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.steamcents.sweep.plist

python3 -m steamprice.sweep --status   # runs, heartbeat, tiers, parked appids
tail -f logs/sweep.log
```

The catalog sync runs on its own daily timer:

```bash
sed "s|__REPO__|$PWD|g" ops/com.steamcents.catalog.plist.template \
  > ~/Library/LaunchAgents/com.steamcents.catalog.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.steamcents.catalog.plist

python3 -m steamprice.catalog --status   # last five syncs and what they changed
```

Every sync writes a `catalog_runs` row, so "syncs daily" is a query rather than a
promise. It refuses to write at all if Steam hands back under 90% of the apps
already live in the database, which is recorded as a `guard` run.

launchd restarts it if it dies, `caffeinate -is` keeps the machine from sleeping on
AC power, and SIGTERM finishes the current batch before exiting. Closing the lid
still sleeps the machine, so leave it open.

To stop it:

```bash
launchctl bootout gui/$(id -u)/com.steamcents.sweep
```

## Layout

```
steamprice/     catalog + sweep
migrations/     apps + price_observations
ops/            launchd plists + run scripts
tests/          fixtures + parse tests
probe.py        early Steam API experiments
```

## License

Nothing fancy yet. Ask if you want to use it.
