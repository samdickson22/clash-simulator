#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1
base=/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1
export PYTHONPATH=$job/source:$job/source/src:$job/eval-ops
export CLASHER_ROOT=$job/source CLASHER_EVAL_RUNTIME_ROOT=$job/source
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME=$job/cache TORCH_HOME=$job/cache/torch TMPDIR=$job/tmp
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1
cd "$job/source"
exec "$base/venv/bin/python" -B "$job/eval-ops/pool.py" --job "$job" "$@"
