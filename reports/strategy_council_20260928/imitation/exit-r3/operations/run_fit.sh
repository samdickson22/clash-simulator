#!/usr/bin/env bash
set -euo pipefail
arm=${1:?}; job=/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1
base=/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1
weight=0
case "$arm" in R3a) ;; R3b) weight=1 ;; *) exit 2 ;; esac
extra=()
if [[ -n ${2:-} ]]; then extra+=(--resume "$2"); fi
export PYTHONPATH=$job/source:$job/source/src PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME=$job/cache CUDA_CACHE_PATH=$job/cache/cuda TORCH_HOME=$job/cache/torch
export TRITON_CACHE_DIR=$job/cache/triton TMPDIR=$job/tmp
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1
export EXIT_LOADER_WORKERS=6 EXIT_LOADER_AMENDMENT=$job/loader6.json
export EXIT_LOADER_AMENDMENT_SHA256
EXIT_LOADER_AMENDMENT_SHA256=$(sha256sum "$EXIT_LOADER_AMENDMENT" | cut -d ' ' -f 1)
cd "$job/source"
exec "$base/venv/bin/python" -B "$job/ops/fit_runtime.py" \
 --init-checkpoint "$job/inputs/main02.pt" --human-store "$base/human/train" \
 --assets "$job/inputs/assets.npz" --teacher-root "$base/corpus" --teacher-ratio 1 \
 --extra-teacher-root "$job/g-corpus/0" --extra-teacher-root "$job/g-corpus/1" \
 --extra-teacher-root "$job/g-corpus/2" --extra-teacher-root "$job/g-corpus/3" \
 --extra-teacher-root "$job/g-corpus/4" \
 --steps 2500 --batch-size 8192 --microbatch 3584 --warmup 2000 --seed 2026101013 \
 --temperature .003 --play-weight 1 --value-weight 0 --advantage-weight "$weight" \
 --checkpoint-every 250 --output "$job/fits/$arm" --stop "$job/FIT.STOP" "${extra[@]}"
