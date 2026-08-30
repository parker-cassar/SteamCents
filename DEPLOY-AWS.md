# Deploying on AWS (us-east-2)

One `t4g.small` EC2 box: Postgres in Docker, sweep on the host under systemd,
read API + Caddy in compose. Terraform provisions the instance, Elastic IP,
security group, and key pair.

## Before you apply

- `aws configure` works for an IAM user (not root access keys).
- `~/.ssh/steamcents` and `~/.ssh/steamcents.pub` exist.
- If you still have Hetzner resources from an old apply, destroy them first:

```bash
cd infra
export TF_VAR_hcloud_token=...   # only for this destroy
terraform init
terraform destroy
```

Remove `infra/.terraform` and `infra/.terraform.lock.hcl` if the provider
switched from hcloud to aws and `terraform init` complains.

If `terraform plan` still tries to refresh Hetzner resources and you no longer
have `TF_VAR_hcloud_token`, drop the orphaned state entries (the real firewall
and key still exist in Hetzner until you delete them in the console):

```bash
terraform state rm hcloud_ssh_key.me hcloud_firewall.fw
```

## Provision

```bash
cd infra
terraform init
terraform apply
terraform output ip
terraform output dns
```

Point `api.steamcents.com` A record at the Elastic IP **now**. Caddy cannot get
a cert until DNS resolves. Propagation often takes 5-15 minutes.

Give cloud-init two or three minutes, then:

```bash
ssh -i ~/.ssh/steamcents deploy@$(terraform output -raw ip)
cloud-init status --wait
```

Repo lands at `/opt/steamcents`.

## Database up

```bash
cd /opt/steamcents
cp .env.example .env
# STEAM_WEB_API_KEY, POSTGRES_PASSWORD, DATABASE_URL matching the password,
# API_DOMAIN=api.steamcents.com, API_ORIGINS for the dashboard origin
docker compose -f docker-compose.prod.yml up -d db
python3 -m steamprice.catalog migrate
```

Postgres binds to `127.0.0.1:5432` only.

## Move the data, do not start fresh

Stop the laptop collectors so the dump is not mid-batch:

```bash
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

Compare those counts against the laptop. Only when they match, leave the laptop
job stopped for good.

## Collectors

```bash
sudo cp ops/systemd/*.service ops/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now steamcents-sweep.service
sudo systemctl enable --now steamcents-catalog.timer
sudo systemctl enable --now steamcents-backup.timer

PYTHONPATH=. python3 -m steamprice.sweep --status
```

Restart the sweep after any code change that affects tiering or parsing.

## Read API

After DNS has propagated:

```bash
docker compose -f docker-compose.prod.yml up -d --build api caddy
curl -s https://api.steamcents.com/health
curl -s https://api.steamcents.com/stats | head -c 400
```

## Costs

This account draws down signup credits, not legacy free-tier hours. A
`t4g.small` plus EBS and the public IPv4 charge is roughly $18/month in
us-east-2. Set a budget alert in the console when you have time.

Backups still land in `backups/` on the same disk. Push dumps off-box (S3 or
your laptop) before credits run out. Price history is not recoverable if you
lose the volume.

## Tear down

```bash
cd infra
terraform destroy
```

This releases the Elastic IP, instance, and security group. EBS volume is
destroyed with the instance unless you changed that in Terraform.
