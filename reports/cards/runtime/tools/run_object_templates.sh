#!/usr/bin/env bash
# Run under cpu_job.sh 4 on 04/08; preserve all prior outputs and reap every child.
set -euo pipefail
J=${CARD_TEMPLATE_JOB:?scratch job}
REPO=${CARD_TEMPLATE_SOURCE:?reviewed source export}
OUT=${CARD_TEMPLATE_OUTPUT:?unique output directory}
export CLASHER_BOT_RUNTIME=${CARD_TEMPLATE_RUNTIME:?isolated scratch runtime}
export CLASHER_BOT_RUNTIME_PINS=live16402b-r3
case "$CLASHER_BOT_RUNTIME" in "$J"/*) ;; *) echo 'runtime outside scratch job' >&2; exit 2;; esac
case "$OUT" in "$J"/*) ;; *) echo 'output outside scratch job' >&2; exit 2;; esac
[[ ! -e "$OUT" ]] || { echo 'output exists; preserve it' >&2; exit 2; }
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 NUMPY_MADVISE_HUGEPAGE=0
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT CLASHER_DELAY_NATIVE_DIR
mkdir "$OUT"
pids=()
for i in 0 1 2 3; do
  nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B \
    "$REPO/reports/cards/runtime/tools/object_templates_probe.py" --shard "$i/4" \
    --out "$OUT/shard-$i.json" > "$OUT/shard-$i.log" 2>&1 & pids+=("$!")
done
rc=0
for pid in "${pids[@]}"; do wait "$pid" || rc=1; done
exit "$rc"
