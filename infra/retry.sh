#!/usr/bin/env bash
set -u

DEADLINE=$(( $(date +%s) + 24*3600 ))
INTERVAL=70
N=0

if [ -z "${TF_VAR_hcloud_token:-}" ]; then
  echo "TF_VAR_hcloud_token not set"; exit 1
fi

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  N=$((N+1))
  printf '[%s] attempt %d ... ' "$(date '+%H:%M:%S')" "$N"
  if terraform apply -auto-approve -input=false -var server_type=cax11 > /tmp/tf-retry.log 2>&1; then
    echo "SUCCESS"
    terraform output -raw ip; echo
    exit 0
  fi
  if grep -q 'unsupported location for server type' /tmp/tf-retry.log; then
    echo "still no ARM capacity (next check $(date -v+${INTERVAL}S '+%H:%M:%S'))"
  else
    echo "FAILED for a different reason, see /tmp/tf-retry.log"
    tail -n 20 /tmp/tf-retry.log
    exit 1
  fi
  sleep "$INTERVAL"
done

echo "24h deadline reached, cax11 never freed up. Switch to cpx22."
exit 1
