# steamcents

Tracks US Steam prices across the whole catalog. Not a deal site. Just a collector that remembers what things cost and when they moved.

Steam's storefront is slow and undocumented if you poke it wrong, so this stays polite: batch `appdetails` (100 ids per request), sleep between calls, back off on 429s. Postgres holds the catalog and a delta-only price history. New / never-checked apps get checked first.

Apps are rechecked on a tier: 6 hours if the price moved in the last two weeks,
24 hours if it is priced and quiet, 7 days if Steam reports no price at all
(free games, videos, hardware, most DLC). Cadences live in `steamprice/config.py`.
About a third of the catalog has no price, and Steam says so with
`{"success": true, "data": []}`, which is a real answer and not a failed request.

## Where it is right now

Numbers from the running instance, all of them queryable rather than claimed.
Regenerate them with `python3 -m steamprice.sweep --status` and the `/stats`
endpoint.

| | |
|---|---|
| apps in the catalog | 247,929 (247,815 live) |
| apps checked at least once | 247,815, so full coverage |
| price observations | 169,178 across 164,464 apps |
| apps Steam reports no price for | about a third of the catalog |
| history starts | 2026-08-21 |
| collection rate | 10 requests/min, 100 ids each, so about 60K apps/hour |
| 429s and errors since run tracking started | 0 and 0 |

Delta-only storage is the point of the schema, and it is measurable: in the
window covered by `sweep_runs`, 51,700 checks produced 5,369 rows, which is
89.6% fewer than storing a snapshot per check. A row only gets written when
the currency, list price, sale price or discount actually differs from the last
one, and `last_checked_at` is stamped either way so nothing jams the queue.

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

## Read API

```bash
pip install -r requirements.txt
PYTHONPATH=. python3 -m uvicorn api.main:app --reload
```

`/health`, `/stats`, `/apps/{appid}`, `/apps/{appid}/history`, `/changes`,
`/changes/daily`, `/drops`. Read only, paginated, CORS limited to the origins in
`API_ORIGINS`. The heavy lifting is in views (`migrations/007_rollups.sql`) so
the handlers stay thin.

## Tests

```bash
PYTHONPATH=. python3 -m pytest -q
```

Needs a Postgres to talk to. It builds a throwaway `steamcents_test` database,
runs every migration into it, and never touches the collection database. CI runs
the same thing against a `postgres:16` service.

## Deploying

See [DEPLOY.md](DEPLOY.md). Terraform for the Hetzner box, Postgres in Docker,
sweep and catalog on the host under systemd, Caddy in front of the API, and a
nightly `pg_dump` with a restore path that is meant to be tested rather than
trusted.

## Layout

```
steamprice/     catalog, sweep, tiering
api/            fastapi read api
migrations/     schema, applied in order with a ledger table
ops/            launchd plists, systemd units, backup script
infra/          terraform for the hetzner box
tests/          fixtures, parse, schedule, sweep, catalog, api
probe.py        early Steam API experiments
```

## License

Nothing fancy yet. Ask if you want to use it.
