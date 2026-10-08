#!/usr/bin/env bash
# Engineering throughput only; no formal admission or heldout entry point.
set -euo pipefail
[[ $(hostname -s) == 127x18 && ${CLASHER_LEASE_ROOT:-} == /mpac/sdicks02/repos/clasher-lease ]] || exit 2
manifest=${1:?verified cache snapshot manifest}; output=${2:?fresh benchmark directory}
workers=${3:-6}
[[ $workers == 6 || $workers == 8 ]] || exit 2
python=$CLASHER_LEASE_ROOT/envs/clasher-gpu/bin/python
code=$CLASHER_ROOT/reports/strategy_council_20260928/live-loop/v4/l1
"$python" -B - "$manifest" "$CLASHER_LEASE_ROOT/data/v4-matches/stage-inventory.json" <<'PY'
import hashlib,json,sys
from pathlib import Path
m=json.loads(Path(sys.argv[1]).read_text());inventory=Path(sys.argv[2])
assert m['complete_for_snapshot'] and m['heldout_payloads_opened'] is False
assert m['source_snapshot_sha256']==hashlib.sha256(inventory.read_bytes()).hexdigest()
assert m['equality_mismatches']==0 and m['files_verified']==2*m['matches']
assert m['equality_checked']>=m['frames']*.01
print('Engineering throughput benchmark; formal fitting/selection remain blocked',flush=True)
PY
exec "$python" -B "$code/train_v4.py" --source "$CLASHER_LEASE_ROOT/data/v4-matches" \
  --split "$CLASHER_ROOT/reports/strategy_council_20260928/live-loop/v4/split.json" \
  --pixel-cache "$CLASHER_LEASE_ROOT/data/v4-cache" --output "$output" \
  --epochs 1 --steps 128 --loader-workers "$workers"
