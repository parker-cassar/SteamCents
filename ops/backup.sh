#!/usr/bin/env bash
# nightly pg_dump. run from the repo root, or via steamcents-backup.timer.
#
# restore into a scratch database and look before you overwrite anything:
#   createdb -h 127.0.0.1 -U steamcents check
#   pg_restore -h 127.0.0.1 -U steamcents -d check --no-owner backups/steamcents-<stamp>.dump
#   psql -h 127.0.0.1 -U steamcents -d check -c 'select count(*) from price_observations'
set -euo pipefail

cd "$(dirname "$0")/.."

DIR=${BACKUP_DIR:-backups}
KEEP=${BACKUP_KEEP:-14}
HOST=${PGHOST:-127.0.0.1}
PORT=${PGPORT:-5432}
USER=${PGUSER:-steamcents}
DB=${PGDATABASE:-steamcents}

mkdir -p "$DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$DIR/steamcents-$STAMP.dump"

# -Fc so pg_restore can do a partial or parallel restore later
pg_dump -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -Fc -f "$OUT.part"
mv "$OUT.part" "$OUT"

# a dump small enough to be an error page or a truncated write is worse than no
# dump, because it looks like a backup
SIZE=$(wc -c < "$OUT" | tr -d ' ')
if [ "$SIZE" -lt 1000000 ]; then
  rm -f "$OUT"
  echo "dump was only $SIZE bytes, threw it away and kept the older ones" >&2
  exit 1
fi

ls -1t "$DIR"/steamcents-*.dump 2>/dev/null | tail -n "+$((KEEP + 1))" | while read -r old; do
  rm -f "$old"
done

echo "$OUT ($SIZE bytes), keeping $KEEP"
