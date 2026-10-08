#!/usr/bin/env bash
# Run on hub after all hub gates pass. Copies, never deletes; one task per target.
set -euo pipefail
[[ $(hostname -s) == 127x01 ]]
base=/mpac/sdicks02
fleet=$base/repos/clasher/reports/strategy_council_20260928/fleet
jobs=$base/jobs/clasher
export CLASHER_FLEET_SOURCE_MANIFEST=$jobs/recovery-source-mac.json
export CLASHER_FLEET_NATIVE_SHA256=$(cat "$jobs/recovery-native.sha256")
.venv/bin/python -B "$fleet/verify_inputs.py"
for label in recovery-bootstrap-20261008 recovery-gates-20261008 recovery-recorded-20261008; do
 [[ $(cat "$jobs/$label.exit") == 0 ]]
done
copy_one() {
 node=$1
 case "$node" in 127x03|127x04|127x07|127x08) ;; *) exit 2;; esac
 ssh "$node" 'hostname; who; mkdir -p /mpac/sdicks02/repos /mpac/sdicks02/tools /mpac/sdicks02/jobs/clasher'
 rsync -az --compress-level=1 --partial --rsync-path="nice -n 10 rsync" "$base/env.sh" "$node:$base/"
 rsync -az --compress-level=1 --partial --rsync-path="nice -n 10 rsync" "$base/tools/" "$node:$base/tools/"
 rsync -azu --compress-level=1 --partial-dir=.rsync-partial --rsync-path="nice -n 10 rsync" --exclude=.rsync-partial/ --exclude=target/ --exclude=__pycache__/ --exclude='*.apk' --exclude='*.apks' --exclude='*.xapk' \
   "$base/repos/clasher/" "$node:$base/repos/clasher/"
 rsync -az --compress-level=1 --partial --rsync-path="nice -n 10 rsync" "$base/repos/clasher-local-data/" "$node:$base/repos/clasher-local-data/"
 for scope in tools repos/clasher repos/clasher-local-data; do
   receipt="$jobs/recovery-verify-$node-${scope//\//_}.log"
   rsync -acni --stats --rsync-path="nice -n 10 rsync" --exclude=target/ --exclude=__pycache__/ --exclude='*.apk' --exclude='*.apks' --exclude='*.xapk' \
     "$base/$scope/" "$node:$base/$scope/" > "$receipt" 2>&1
   if grep -E '^[<>ch.*][fdLDS]' "$receipt"; then echo "Checksum mismatch: $node $scope" >&2; return 1; fi
 done
 rsync -a --rsync-path="nice -n 10 rsync" "$jobs/transfer-ready.json" "$jobs/recovery-source-mac.json" "$jobs/recovery-native.sha256" "$node:$jobs/"
 ssh "$node" "who; bash '$fleet/fleet_run.sh' recovery-smoke-$node-20261008 env CLASHER_FLEET_SOURCE_MANIFEST='$CLASHER_FLEET_SOURCE_MANIFEST' CLASHER_FLEET_NATIVE_SHA256='$CLASHER_FLEET_NATIVE_SHA256' bash '$fleet/smoke.sh'"
}
if [[ ${1:-} == --node ]]; then copy_one "$2"; exit; fi
for node in 127x03 127x04 127x07 127x08; do
 bash "$fleet/fleet_run.sh" "recovery-copy-$node-20261008" bash "$fleet/fanout.sh" --node "$node"
done
