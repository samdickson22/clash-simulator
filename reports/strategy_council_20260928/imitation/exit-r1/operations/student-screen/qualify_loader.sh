#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1
export PYTHONPATH=$job/source:$job/source/src PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME=$job/cache CUDA_CACHE_PATH=$job/cache/cuda TORCH_HOME=$job/cache/torch
export TRITON_CACHE_DIR=$job/cache/triton TMPDIR=$job/tmp
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1
export EXIT_LOADER_AMENDMENT=$job/student-owned-gpu-amendment-v2.json
export EXIT_LOADER_AMENDMENT_SHA256=23e63c3c70e9eaa7c5ded4c1f79300ee9eb515fbbf98721e3a46c45d6e752abf
exec "$job/venv/bin/python" -B "$job/ops/qualify_loader.py" --job "$job" --arm "$1" --ratio "$2" --resume "$3"
