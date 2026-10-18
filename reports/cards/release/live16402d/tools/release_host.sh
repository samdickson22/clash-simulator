#!/usr/bin/env bash
# Create + verify r1-cards4 and live16402d on THIS host (127x04/127x08) from JOB/publish-inputs.
#   cpu_job.sh 1 bash release_host.sh JOB SUMMARY_SHA256 SOURCE_SHA256
# Launch only after JOB/SUMMARY.json (summarize.py) is PASS for the FINAL source/native. Existing targets stop.
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -euo pipefail
J=${1:?job} SUMMARY_SHA=${2:?SUMMARY.json sha256} SOURCE_SHA=${3:?publish-inputs/SOURCE.json sha256}
case $(hostname -s) in 127x04|127x08) ;; *) echo "wrong host" >&2; exit 2;; esac
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
T=$(cd "$(dirname "$0")" && pwd)
export PYTHONOPTIMIZE=0 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 NUMPY_MADVISE_HUGEPAGE=0
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT CLASHER_DELAY_NATIVE_DIR
"$PY" -B - "$J" "$SUMMARY_SHA" <<'PY'
import hashlib, json, sys
from pathlib import Path
j = Path(sys.argv[1]); sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(j / 'SUMMARY.json') == sys.argv[2], 'summary pin'
s = json.loads((j / 'SUMMARY.json').read_text())
a = json.loads((j / 'ASSEMBLY.json').read_text())
assert s['result'] == 'PASS' and s['headline']['identical'] == 12 and s['class']['exceptions'] == 0
assert s['mixed']['crashes'] == 0 and s['mixed']['root_errors'] == 0 and s['graph_class']['candidate_graph_errors'] == 0
assert s['engine_commit'] == a['source_commit'][:len(s['engine_commit'])]
PY
for n in r1-cards4 live16402d; do
  p=/mpac/sdicks02/repos/clasher-bot-runtime/$n
  [[ ! -e "$p" && ! -L "$p" ]] || { echo "TARGET_EXISTS_STOP $p" >&2; exit 2; }
done
for n in r1-cards4 live16402d; do
  nice -n 15 "$PY" -B "$T/release.py" create --job "$J" --name "$n" --source-sha "$SOURCE_SHA"
  nice -n 15 "$PY" -B "$T/release.py" verify --job "$J" --name "$n" --source-sha "$SOURCE_SHA"
done
echo RELEASE HOST DONE "$(hostname -s)"
