# Deploying steamcents

One Hetzner box running Postgres in Docker, with the sweep and the catalog sync
on the host under systemd. Same shape as the laptop, so nothing surprising moves.

## Provision

You need a Hetzner Cloud API token and the `steamcents` ssh key pair.

```bash
cd infra
export TF_VAR_hcloud_token=...
terraform init
terraform apply -var acme_email=you@example.com
```

Defaults to `cpx22` in `nbg1`. `cax11` is ARM and cheaper, but nbg1 capacity for
it comes and goes, so it is not the default. To try it anyway:

```bash
terraform apply -var server_type=cax11 -var acme_email=you@example.com
```

If that fails with "unsupported location for server type" the capacity is not
there. `infra/retry.sh` will keep trying for 24 hours. Do not wait on it, take
the cpx22.

`terraform output` gives you the IP and the ssh command. Point
`api.steamcents.com` at the IP now, because Caddy cannot get a certificate until
the DNS resolves.

Cloud-init installs Docker, makes a `deploy` user, sets up ufw, and clones the
repo to `/opt/steamcents`. Give it two or three minutes and watch it land:

```bash
ssh -i ~/.ssh/steamcents deploy@$(terraform output -raw ip)
cloud-init status --wait
```

## Bring up the database

```bash
cd /opt/steamcents
cp .env.example .env
# set STEAM_WEB_API_KEY, a real POSTGRES_PASSWORD, and DATABASE_URL to match
docker compose -f docker-compose.prod.yml up -d
python3 -m steamprice.catalog migrate
```

Postgres binds to `127.0.0.1:5432` only. It is not reachable from outside the
box, and the hcloud firewall plus ufw only allow 22, 80 and 443 anyway.

## Move the data over, do not start fresh

There are months of `last_checked_at` and a full catalog pass on the laptop.
Starting clean throws away the history the whole project is for.

On the laptop, stop the collectors first so the dump is not mid-batch:

```bash
launchctl bootout gui/$(id -u)/com.steamcents.sweep
launchctl bootout gui/$(id -u)/com.steamcents.catalog
PGPASSWORD=steamcents ops/backup.sh
scp -i ~/.ssh/steamcents backups/steamcents-*.dump deploy@BOX:/opt/steamcents/backups/
```

On the box:

```bash
cd /opt/steamcents
pg_restore -h 127.0.0.1 -U steamcents -d steamcents --no-owner --clean --if-exists \
  backups/steamcents-<stamp>.dump
psql -h 127.0.0.1 -U steamcents -d steamcents -c \
  'select count(*) from apps, (select 1) x' -c 'select count(*) from price_observations'
```

Compare those two counts against the laptop before you go any further. Only once
they match do you leave the laptop job stopped for good.

## Start the collectors

```bash
sudo cp ops/systemd/*.service ops/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now steamcents-sweep.service
sudo systemctl enable --now steamcents-catalog.timer
sudo systemctl enable --now steamcents-backup.timer

systemctl status steamcents-sweep
systemctl list-timers 'steamcents*'
PYTHONPATH=. python3 -m steamprice.sweep --status
```

`steamcents-sweep.service` stops with SIGTERM and a 120 second grace period, so
`systemctl restart` finishes the batch it is holding and closes its `sweep_runs`
row instead of leaving an ambiguous half-written one.

## Backups

`ops/backup.sh` runs nightly at 03:30 via `steamcents-backup.timer`. It writes a
`-Fc` dump to `backups/`, keeps 14, and refuses to rotate the older ones if the
new dump comes out under a megabyte, because a truncated dump that looks like a
backup is worse than a missing one.

Test the restore rather than assuming it. Into a scratch database, never over the
live one:

```bash
createdb -h 127.0.0.1 -U steamcents check
pg_restore -h 127.0.0.1 -U steamcents -d check --no-owner backups/steamcents-<stamp>.dump
psql -h 127.0.0.1 -U steamcents -d check -c 'select count(*) from price_observations'
dropdb -h 127.0.0.1 -U steamcents check
```

The dumps live on the same disk as the database, which is not a real offsite
backup. Push them somewhere else before you rely on them.

## The read API

Not deployed yet. When `api/` lands, a Caddy service in
`docker-compose.prod.yml` terminates TLS on `api.steamcents.com` and proxies to
it. That is why the firewall opens 80 and 443 and why the DNS record wants to be
in place early: Caddy needs the name to resolve before Let's Encrypt will issue.

## Rolling out a change

```bash
cd /opt/steamcents && git pull
python3 -m steamprice.catalog migrate
sudo systemctl restart steamcents-sweep
```

The migration runner is a sorted glob with a `schema_migrations` ledger, so it is
safe to run every deploy. The sweep runs whatever code was loaded when it
started, so a change to tiering or parsing does nothing at all until you restart
it. Check with `--status` that the run id actually changed.
