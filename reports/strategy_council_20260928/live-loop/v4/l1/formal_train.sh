#!/usr/bin/env bash
# Invoke through fleet_run.sh or the lease wrapper; authentic T1 receipts only.
set -euo pipefail
arm=${1:?t6 or t7}; state=${2:?T1 pipeline-state.json}; receipt=${3:?T1 phase-a-exit.json}; destination=${4:?fresh output directory}
host=$(hostname -s)
case $host in
  127x01) root=/mpac/sdicks02/repos/clasher; python=/mpac/sdicks02/envs/clasher-gpu/bin/python; source=/mpac/sdicks02/repos/clasher-v4-data/matches ;;
  127x09|127x11|127x13|127x14|127x15|127x16|127x18)
    [[ ${CLASHER_LEASE_ROOT:-} == /mpac/sdicks02/repos/clasher-lease ]] || { echo 'Lease wrapper/env required' >&2; exit 2; }
    root=$CLASHER_LEASE_ROOT/repo; python=$CLASHER_LEASE_ROOT/envs/clasher-gpu/bin/python
    source=$CLASHER_LEASE_ROOT/data/v4-matches ;;
  *) echo 'Host not authorized' >&2; exit 2 ;;
esac
cache=${5:-}; prepared_t6=${6:-}
code=$root/reports/strategy_council_20260928/live-loop/v4/l1
split=$root/reports/strategy_council_20260928/live-loop/v4/split.json
[[ $arm == t6 || $arm == t7 ]] || exit 2
# Reserve four process slots; count existing Python workers conservatively.
if [[ $host == 127x01 ]]; then
  workers=$(ps -u "$(id -un)" -o comm= | awk '$1 ~ /^python/ {n++} END {print n+0}')
else
  # Owner/roader Python processes do not consume the borrower's lease cap.
  # run.sh's host-wide lock excludes another supervised Clasher workload;
  # lease_watch.py independently counts all descendants/RSS throughout the job.
  workers=$(ps -u "$(id -un)" -o args= | awk '/clasher-lease/ && !/awk/ && !/sshd/ {n++} END {print n+0}')
fi
cap=96
case $host in 127x09|127x15) cap=8 ;; 127x13|127x14) cap=64 ;; 127x16|127x18) cap=48 ;; esac
console_users=$("$HOME/.local/bin/fleet-console-users")
[[ $console_users =~ ^[0-9]+$ ]] || { echo 'Invalid console-cap helper response' >&2; exit 2; }
(( console_users == 0 )) || cap=16
case $host in 127x09|127x15) cap=8 ;; esac
(( workers + 4 <= cap )) || { echo "Host worker capacity exceeded: $workers + 4 > $cap" >&2; exit 75; }
free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
(( free >= 16384 )) || { echo 'Need >=16GiB free GPU memory' >&2; exit 75; }
[[ ! -e $destination ]] || { echo 'Fresh output directory required' >&2; exit 2; }
if [[ $arm == t7 ]]; then
  [[ -d $cache ]] || { echo 'Validated lossless cache required for formal T7' >&2; exit 2; }
fi
case $host in 127x09|127x15)
  [[ $arm != t6 || -f $prepared_t6/complete.json ]] || { echo 'GPU-only host requires preconverted T6 data' >&2; exit 2; } ;;
esac
mkdir -p "$destination"
"$python" "$code/formal_guard.py" --phase-state "$state" --phase-exit "$receipt" --source "$source" --split "$split" --output "$destination/admission.json"
if [[ $arm == t6 ]]; then
  if [[ -z $prepared_t6 ]]; then
    "$python" "$code/prepare_t6.py" --source "$source" --split "$split" --output "$destination/dataset" --workers 2
    prepared_t6=$destination/dataset
  fi
  "$python" - "$source" "$prepared_t6" <<'PY'
import json,sys
from pathlib import Path
source,dataset=map(Path,sys.argv[1:])
expected={r['episode'] for p in source.glob('*/receipt.json') if (r:=json.loads(p.read_text())).get('split') in ('train','validation')}
inventory=json.loads((dataset/'inventory.json').read_text())
if {r['episode'] for r in inventory}!=expected:raise ValueError('Prepared T6 population differs from full admitted Phase A')
for r in inventory:
    import hashlib
    if hashlib.sha256((source/r['episode']/'receipt.json').read_bytes()).hexdigest()!=r['receipt_sha256']:raise ValueError('Prepared T6 receipt changed')
PY
  "$python" "$code/run_t6_shake.py" --dataset "$prepared_t6" --output "$destination/run" --epochs 24 --steps 400 --pixel-cache-mib 4096
else
  "$python" "$code/train_v4.py" --source "$source" --split "$split" --output "$destination/model" --epochs 24 --steps 400 --pixel-cache "$cache" --loader-workers 6
fi
