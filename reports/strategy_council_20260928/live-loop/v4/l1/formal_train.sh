#!/usr/bin/env bash
# Invoke through fleet_run.sh or the lease wrapper; authentic T1 receipts only.
# Pool-mode admission (2026-10-08): pass t1-completion-mirror/pool-state.json
# and T1-PHASE-A-COMPLETE.json. formal_guard.admit verifies the mirror's hashes,
# coverage stop, real pool exit0 and stopped-process evidence. Pool mode has no
# legacy phase-a-exit.json; the stale pre-pool pipeline state is not substituted.
set -euo pipefail
arm=${1:?t6 or t7}; state=${2:?Authentic T1 producer state}; receipt=${3:?T1 pool completion manifest or pipeline exit receipt}; destination=${4:?fresh output directory}
host=$(hostname -s)
case $host in
  127x09|127x15)
    [[ ${CLASHER_LEASE_ROOT:-} == /mpac/sdicks02/repos/clasher-lease ]] || { echo 'Lease wrapper/env required' >&2; exit 2; }
    [[ ${CLASHER_V4_RUN_SUPERVISED:-} == 1 ]] || { echo 'lease_lifecycle_v4.py required for hourly backup/deadline' >&2; exit 2; }
    root=$CLASHER_LEASE_ROOT/repo; python=$CLASHER_LEASE_ROOT/envs/clasher-gpu/bin/python
    source=$CLASHER_LEASE_ROOT/data/v4-matches ;;
  *) echo 'Coordinator assigns T7 to 09 and T6 to 15; 01 GPU belongs to T5' >&2; exit 2 ;;
esac
[[ $host:$arm == 127x09:t7 || $host:$arm == 127x15:t6 ]] || { echo 'Wrong arm for assigned GPU' >&2; exit 2; }
cache=${5:-}; prepared_t6=${6:-}; continuation=${7:-}
[[ -z $continuation || $arm:$continuation == t7:resume ]] || { echo 'Only T7 optimizer/RNG resume supported' >&2; exit 2; }
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
cap=$("$python" - "$host" <<'PY'
import json,sys
from pathlib import Path
lease=json.loads((Path('/mpac/sdicks02/fleet-leases')/(sys.argv[1]+'.json')).read_text())
if lease.get('cpu') is not True or lease.get('gpu_only') is not False:raise ValueError('CPU-expanded lease required')
print(min(96,int(lease['max_workers'])))
PY
)
console_users=$("$HOME/.local/bin/fleet-console-users")
[[ $console_users =~ ^[0-9]+$ ]] || { echo 'Invalid console-cap helper response' >&2; exit 2; }
(( console_users == 0 )) || cap=16
(( workers + 4 <= cap )) || { echo "Host worker capacity exceeded: $workers + 4 > $cap" >&2; exit 75; }
free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
(( free >= 16384 )) || { echo 'Need >=16GiB free GPU memory' >&2; exit 75; }
if [[ $continuation == resume ]]; then
  [[ -f $destination/model/last.pt && -f $destination/admission.json ]] || { echo 'Existing T7 checkpoint/admission required' >&2; exit 2; }
else
  [[ ! -e $destination ]] || { echo 'Fresh output directory required' >&2; exit 2; }
fi
if [[ $arm == t7 ]]; then
  [[ -f $cache ]] || { echo 'Pinned full-population cache union connection file required for formal T7' >&2; exit 2; }
fi
mkdir -p "$destination"
if [[ $continuation == resume ]]; then
  "$python" - "$code" "$state" "$receipt" "$source" "$split" "$destination/admission.json" <<'PY'
import sys,json
from pathlib import Path
code,state,ex,source,split,proof=map(Path,sys.argv[1:]);sys.path.insert(0,str(code))
from formal_guard import admit
if admit(state,ex,source,split,code)!=json.loads(proof.read_text()):raise ValueError('Resume producer/population changed')
PY
else
  "$python" "$code/formal_guard.py" --phase-state "$state" --phase-exit "$receipt" --source "$source" --split "$split" --output "$destination/admission.json"
fi
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
  "$python" "$code/run_t6_shake.py" --dataset "$prepared_t6" --output "$destination/run" --epochs 24 --steps 400 --pixel-cache-mib 4096 --pixel-cache-directory "$CLASHER_LEASE_ROOT/data/v4-cache/t6-$(basename "$destination")"
else
  extra=(); [[ $continuation != resume ]] || extra=(--resume)
  "$python" "$code/train_v4.py" --source "$source" --split "$split" --output "$destination/model" --epochs 24 --steps 400 --formal-union "$cache" --phase-state "$state" --phase-exit "$receipt" --loader-workers 6 "${extra[@]}"
fi
