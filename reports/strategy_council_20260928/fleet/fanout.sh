#!/usr/bin/env bash
# Run on hub after all hub gates pass. Copies, never deletes; one task per target.
set -euo pipefail
[[ $(hostname -s) == 127x02 ]]
base=/mpac/sdicks02
fleet=$base/repos/clasher/reports/strategy_council_20260928/fleet
jobs=$base/jobs/clasher
.venv/bin/python -B "$fleet/verify_inputs.py"
for label in bootstrap-20261007-r3 gate-sequence-linux-20261007 recorded-linux-20261007 stage6-resolved-linux-20261007-r2; do
 [[ $(cat "$jobs/$label.exit") == 0 ]]
done
copy_one() {
 node=$1
 case "$node" in 127x01|127x03|127x04|127x07|127x08) ;; *) exit 2;; esac
 ssh "$node" 'hostname; who; mkdir -p /mpac/sdicks02/repos /mpac/sdicks02/tools /mpac/sdicks02/jobs/clasher'
 rsync -az --compress-level=1 --partial --rsync-path="nice -n 10 rsync" "$base/env.sh" "$node:$base/"
 rsync -az --compress-level=1 --partial --rsync-path="nice -n 10 rsync" "$base/tools/" "$node:$base/tools/"
 rsync -az --compress-level=1 --partial --rsync-path="nice -n 10 rsync" --exclude=target/ --exclude=__pycache__/ --exclude='*.apk' --exclude='*.apks' --exclude='*.xapk' \
   "$base/repos/clasher/" "$node:$base/repos/clasher/"
 rsync -az --compress-level=1 --partial --rsync-path="nice -n 10 rsync" "$base/repos/clasher-local-data/" "$node:$base/repos/clasher-local-data/"
 rsync -a --rsync-path="nice -n 10 rsync" "$jobs/transfer-ready.json" "$node:$jobs/"
 ssh "$node" "bash '$fleet/fleet_run.sh' smoke-p16-linux-20261007 bash '$fleet/smoke.sh'"
}
if [[ ${1:-} == --node ]]; then copy_one "$2"; exit; fi
for node in 127x01 127x03 127x04 127x07 127x08; do
 bash "$fleet/fleet_run.sh" "copy-$node-20261007" bash "$fleet/fanout.sh" --node "$node"
done
