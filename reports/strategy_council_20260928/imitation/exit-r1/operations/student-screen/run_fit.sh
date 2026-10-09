#!/usr/bin/env bash
set -euo pipefail
arm=${1:?}; ratio=${2:?}
job=/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1
export PYTHONPATH=$job/source:$job/source/src
export PYTHONDONTWRITEBYTECODE=1 XDG_CACHE_HOME=$job/cache CUDA_CACHE_PATH=$job/cache/cuda
export TORCH_HOME=$job/cache/torch TRITON_CACHE_DIR=$job/cache/triton TMPDIR=$job/tmp
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1
cd "$job/source"
exec "$job/venv/bin/python" -B "$job/ops/fit_runtime.py" \
  --init-checkpoint "$job/inputs/main02.pt" --human-store "$job/human/train" \
  --assets "$job/inputs/assets.npz" --teacher-root "$job/corpus" --teacher-ratio "$ratio" \
  --steps 4883 --batch-size 8192 --microbatch 7168 --warmup 2000 --seed 2026100901 \
  --temperature 0.1 --play-weight 4 --value-weight 0 --checkpoint-every 1000 \
  --output "$job/fits/$arm" --stop "$job/FIT.STOP"
