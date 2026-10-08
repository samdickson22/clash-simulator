#!/usr/bin/env bash
# Run through fleet_run.sh on 127x01. Mac is read-only; all logs are on the hub.
set -euo pipefail
[[ $(hostname -s) == 127x01 ]]
base=/mpac/sdicks02
root=$base/repos/clasher
jobs=$base/jobs/clasher
src=/Users/sam/Desktop/code/clasher
export RSYNC_RSH='ssh -T -o BatchMode=yes -o Compression=no -o ControlMaster=no -o ControlPath=none'
ex=(--exclude=/.venv/ --exclude=target/ --exclude='*.so' --exclude='*.dylib' --exclude=__pycache__/ --exclude=node_modules/ --exclude=.DS_Store --exclude='*.apk' --exclude='*.apks' --exclude='*.xapk')
common=(-a --partial --stats --rsync-path='nice -n 19 /opt/homebrew/bin/rsync')
who
ssh macmini-fleet who
# Two streams keep the logged-in Mac console users' load light.
rsync "${common[@]}" "${ex[@]}" --exclude=/artifacts/ "macmini-fleet:$src/" "$root/" > "$jobs/recovery-copy-repo.log" 2>&1 &
repo_pid=$!
rsync "${common[@]}" "${ex[@]}" "macmini-fleet:$src/artifacts/" "$root/artifacts/" > "$jobs/recovery-copy-artifacts.log" 2>&1 &
artifact_pid=$!
rc=0
wait "$repo_pid" || rc=1
wait "$artifact_pid" || rc=1
[[ $rc == 0 ]]
mkdir -p "$base/repos/clasher-local-data"
for item in clasher-engine-speed clasher-native-reference/decoded-logic-1e505767; do
  rsync "${common[@]}" --exclude='*.apk' --exclude='*.apks' --exclude='*.xapk' "macmini-fleet:/Users/sam/.cache/$item" "$base/repos/clasher-local-data/"
done
rsync "${common[@]}" "${ex[@]}" "macmini-fleet:$src/" "$root/" > "$jobs/recovery-final-sweep.log" 2>&1
rsync "${common[@]}" -cni "${ex[@]}" "macmini-fleet:$src/" "$root/" > "$jobs/recovery-verify-repo.log" 2>&1
for item in clasher-engine-speed clasher-native-reference/decoded-logic-1e505767; do
  rsync "${common[@]}" -cni --exclude='*.apk' --exclude='*.apks' --exclude='*.xapk' "macmini-fleet:/Users/sam/.cache/$item" "$base/repos/clasher-local-data/" > "$jobs/recovery-verify-${item##*/}.log" 2>&1
done
if grep -E '^[<>ch.*][fdLDS]' "$jobs"/recovery-verify-*.log; then
  echo 'Source changed or copy mismatch; inspect and repeat verification.' >&2
  exit 1
fi
date -u +%FT%TZ
