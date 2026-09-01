# Deploying steamcents

One `t4g.small` EC2 box in **us-east-2**: Postgres in Docker, sweep and catalog on
the host under systemd, read API and Caddy in compose. Terraform provisions the
instance, Elastic IP, security group, key pair, and an S3 bucket for offsite
dumps.

## Before you apply

- `aws configure` works for an IAM user (not root access keys), region
  `us-east-2`.
- `~/.ssh/steamcents` and `~/.ssh/steamcents.pub` exist.
- If old Hetzner state is still in `terraform.tfstate`, destroy or drop it:

```bash
cd infra
export TF_VAR_hcloud_token=...   # only if you still have it
terraform destroy
```

Or without a Hetzner token (orphaned state only; delete the real resources in
the Hetzner console later):

```bash
terraform state rm hcloud_ssh_key.me hcloud_firewall.fw
```

## Provision

Elastic IP is created before the instance so you can set DNS while the box
boots:

```bash
cd infra
terraform init
terraform apply -target=aws_eip.app -auto-approve
terraform output -raw ip
```

Point `api.steamcents.com` A record at that IP **now** (Porkbun or wherever the
domain lives). Caddy cannot get a cert until DNS resolves. Propagation often
takes 5-15 minutes.

Then bring up the rest:

```bash
terraform apply -auto-approve
terraform output ip
terraform output backup_bucket
```

Cloud-init clones the public repo URL in Terraform. If the repo is private, rsync
from your laptop after the instance is up:

```bash
rsync -az -e "ssh -i ~/.ssh/steamcents" \
  --exclude '.git' --exclude '.venv' --exclude 'logs' --exclude 'backups' \
  ./ deploy@$(terraform output -raw ip):/opt/steamcents/
```

Your `~/.ssh/steamcents` key is passphrase-protected. Run `ssh-add
~/.ssh/steamcents` once per session, or use EC2 Instance Connect (the deploy
user accepts a one-time key pushed by the AWS CLI).

Porkbun: add an **A** record for host `api` pointing at the Elastic IP. Remove
any parking-page or URL-forward on that hostname. Let's Encrypt will fail until
`dig api.steamcents.com` returns the EIP, not Porkbun's `207.207.210.x` addresses.

## Database up (empty schema only, not a fresh crawl)

```bash
cd /opt/steamcents
cp .env.example .env
# STEAM_WEB_API_KEY, POSTGRES_PASSWORD, DATABASE_URL matching the password,
# API_DOMAIN=api.steamcents.com, API_ORIGINS for the dashboard origin
docker compose -f docker-compose.prod.yml up -d db
python3 -m steamprice.catalog migrate
```

Postgres binds to `127.0.0.1:5432` only. **Do not start the sweep yet.** An
empty migrated database is not a working system for this project.

## Move the data, do not start fresh

The laptop still has the real history. Keep the launchd collectors running until
you have restored on the box and the counts match. Only stop them for the dump
itself so it is not mid-batch.

On the laptop, record counts, then stop collectors and dump:

```bash
docker compose up -d   # if postgres is in docker locally
docker exec steam_price-db-1 psql -U steamcents -d steamcents -t \
  -c 'select count(*) from apps' \
  -c 'select count(*) from price_observations'

launchctl bootout gui/$(id -u)/com.steamcents.sweep
launchctl bootout gui/$(id -u)/com.steamcents.catalog
PGPASSWORD=steamcents ops/backup.sh
scp -i ~/.ssh/steamcents backups/steamcents-*.dump \
  deploy@$(terraform output -raw ip):/opt/steamcents/backups/
```

On the box:

```bash
cd /opt/steamcents
pg_restore -h 127.0.0.1 -U steamcents -d steamcents --no-owner --clean --if-exists \
  backups/steamcents-<stamp>.dump
psql -h 127.0.0.1 -U steamcents -d steamcents -c 'select count(*) from apps' \
  -c 'select count(*) from price_observations'
```

Those two counts must match the laptop numbers from before the dump. If they
do not, fix the restore before starting anything on the box. Only then leave the
laptop collectors stopped for good.

## Collectors on the box

```bash
sudo cp ops/systemd/*.service ops/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now steamcents-sweep.service
sudo systemctl enable --now steamcents-catalog.timer
sudo systemctl enable --now steamcents-backup.timer

PYTHONPATH=. python3 -m steamprice.sweep --status
```

Restart the sweep after any code change that affects tiering or parsing.
`systemctl restart` sends SIGTERM; the sweep finishes the in-flight batch and
closes its `sweep_runs` row.

## Read API

After DNS has propagated:

```bash
docker compose -f docker-compose.prod.yml up -d --build api caddy
curl -s https://api.steamcents.com/health
curl -s https://api.steamcents.com/stats | head -c 400
```

If Caddy cannot get a certificate, check that `api.steamcents.com` resolves to
the Elastic IP, then `docker compose -f docker-compose.prod.yml logs caddy`.

## Backups

`ops/backup.sh` runs nightly at 03:30 via `steamcents-backup.timer`. It writes a
`-Fc` dump to `backups/`, keeps 14 locally, refuses dumps under a megabyte, and
copies each good dump to the Terraform-managed S3 bucket (`terraform output
backup_bucket`). The EC2 instance role has write access; no keys on disk.

Test a restore into a scratch database, never over the live one:

```bash
createdb -h 127.0.0.1 -U steamcents check
pg_restore -h 127.0.0.1 -U steamcents -d check --no-owner backups/steamcents-<stamp>.dump
psql -h 127.0.0.1 -U steamcents -d check -c 'select count(*) from price_observations'
dropdb -h 127.0.0.1 -U steamcents check
```

## Costs

Signup credits draw down with usage, not legacy free-tier hours. A `t4g.small`
plus EBS and the public IPv4 charge is roughly $18/month in us-east-2. S3 for
a few hundred MB of dumps is cents. Set a budget alert when you have time.

## Tear down

```bash
cd infra
terraform destroy
```

Releases the Elastic IP, instance, security group, and S3 bucket (dumps inside
it). EBS is destroyed with the instance.

## Rolling out a change

```bash
cd /opt/steamcents && git pull
python3 -m steamprice.catalog migrate
sudo systemctl restart steamcents-sweep
```

Check with `--status` that the run id actually changed.
