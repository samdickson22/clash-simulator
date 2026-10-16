#!/usr/bin/env bash
# Launch only after the exact full-v3 aggregate receipt is PASS.
set -euo pipefail
J=${1:?scratch job}
GATES_SHA=${2:?aggregate gate receipt SHA256}
SOURCE_SHA=ccb6a89141cfcbd9344aa4e61978b8b1167c6f029e97083a0863b2c9892f6563
TOOL_SHA=0b2afd9cf99a40b59e749bf15b819dc62d9d11290f701b0248b7bf37d19a23e8
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
export PYTHONOPTIMIZE=0 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 NUMPY_MADVISE_HUGEPAGE=0
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT CLASHER_DELAY_NATIVE_DIR
"$PY" -B - "$J" "$GATES_SHA" "$TOOL_SHA" <<'PY'
import hashlib,json,sys
from pathlib import Path
j=Path(sys.argv[1]);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(j/'GATES.json')==sys.argv[2]
assert sha(j/'release.py')==sys.argv[3]
g=json.loads((j/'GATES.json').read_text())
assert g['result']=='PASS'
assert g['class']['cards']==122 and g['class']['scenarios']==366 and g['class']['exceptions']==0
assert g['headline']['identical']==12
PY
for n in r1-cards3 live16402c; do
 p=/mpac/sdicks02/repos/clasher-bot-runtime/$n
 [[ ! -e "$p" && ! -L "$p" ]] || { echo "TARGET_EXISTS_STOP $p" >&2; exit 2; }
done
for n in r1-cards3 live16402c; do
 nice -n 15 "$PY" -B "$J/release.py" create --job "$J" --name "$n" --source-sha "$SOURCE_SHA"
 nice -n 15 "$PY" -B "$J/release.py" verify --job "$J" --name "$n" --source-sha "$SOURCE_SHA"
done
