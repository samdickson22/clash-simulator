#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2
base=/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1
export PYTHONPATH=$job/eval-source:$job/eval-source/src:$job/student-source:$job/eval-ops
export CLASHER_ROOT=$job/eval-source CLASHER_EVAL_RUNTIME_ROOT=$job/eval-source
export CLASHER_DELAY_NATIVE_DIR=$job/reporting-native CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME=$job/cache TORCH_HOME=$job/cache/torch TMPDIR=$job/tmp
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1
cd "$job/eval-source"
exec "$base/venv/bin/python" -B "$job/eval-ops/pool.py" --job "$job" "$@"
