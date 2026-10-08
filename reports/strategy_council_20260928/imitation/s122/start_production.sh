#!/usr/bin/env bash
set -euo pipefail
cd /mpac/sdicks02/repos/clasher
base=reports/strategy_council_20260928/imitation
jobs=/mpac/sdicks02/jobs/clasher
host=$(hostname -s)
case "$host" in 127x01) partition=1;; 127x03) partition=0;; *) exit 2;; esac
receipt() {
  local node=$1 label=$2
  if [[ "$node" == "$host" ]]; then cat "$jobs/$label.exit" 2>/dev/null || true
  else ssh -o BatchMode=yes -o ConnectTimeout=10 "$node" "cat $jobs/$label.exit 2>/dev/null" || true
  fi
}
while [[ ! -f "$base/data/receipts/T10-QA-PASS.json" ]]; do
  rc=$(receipt 127x01 imitation-s122-qa-finish-20261008-r1)
  [[ -z "$rc" || "$rc" == 0 ]] || { echo 'QA gates failed'; exit 1; }
  sleep 30
done
while true; do
  rc=$(receipt 127x03 imitation-s122-pack-mirror-20261008-r2)
  [[ -z "$rc" ]] || break
  sleep 30
done
[[ "$rc" == 0 ]] || { echo 'Input packing/copy failed'; exit 1; }
exec .venv/bin/python "$base/s122/extract_s122.py" production --workers 78 --partition "$partition" --partitions 2
