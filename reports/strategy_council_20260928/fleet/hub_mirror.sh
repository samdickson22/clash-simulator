#!/usr/bin/env bash
# Persistent copy-only backup. Launch via fleet_run.sh; no system scheduler changes.
set -euo pipefail
[[ $(hostname -s) == 127x01 ]]
base=/mpac/sdicks02
jobs=$base/jobs/clasher
reports=$base/repos/clasher/reports/strategy_council_20260928
if [[ ${1:-} != --nice ]]; then exec nice -n 19 bash "$0" --nice; fi
paths=("$base/repos/clasher-v4-data" "$jobs" "$reports/c56/data/recon" "$reports/search-noise-v2" "$reports/engine-speed")
while true; do
  date -u +%FT%TZ
  who
  status=0
  ssh -o BatchMode=yes -o ConnectTimeout=15 127x04 who || status=1
  for path in "${paths[@]}"; do
    if [[ ! -d "$path" ]]; then echo "missing source: $path"; status=1; continue; fi
    ssh -o BatchMode=yes -o ConnectTimeout=15 127x04 "mkdir -p '$path'" || { status=1; continue; }
    # Mutable logs/data can vanish during a cycle; retain the exit in the heartbeat.
    rsync -au --partial-dir=.rsync-partial --exclude=.rsync-partial/ --bwlimit=51200 --timeout=120 --rsync-path='nice -n 19 rsync' \
      --exclude='*.apk' --exclude='*.apks' --exclude='*.xapk' \
      -e 'ssh -o BatchMode=yes -o ConnectTimeout=15' "$path/" "127x04:$path/" || status=1
  done
  printf '{"utc":"%s","hub":"127x01","mirror":"127x04","cycle_exit":%s}\n' "$(date -u +%FT%TZ)" "$status" > "$jobs/hub-mirror-heartbeat.json.tmp"
  mv "$jobs/hub-mirror-heartbeat.json.tmp" "$jobs/hub-mirror-heartbeat.json"
  cat "$jobs/hub-mirror-heartbeat.json"
  sleep 1800
done
