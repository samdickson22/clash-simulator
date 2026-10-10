#!/usr/bin/env bash
set -euo pipefail
arm=${1:?}; job=${EXIT_R2_JOB:-/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1}
ratio=1.0; temperature=0.003; steps=4883; micro=7168; extra=()
case $arm in
  X1) ;;
  X2) temperature=0.0001 ;;
  X3) temperature=0.5; extra=(--score-zscore) ;;
  X4) ratio=0.75; micro=3584 ;;
  X5) steps=9766 ;;
  *) echo 'Unknown X arm' >&2; exit 1 ;;
esac
if [[ -n ${2:-} ]]; then extra+=(--resume "$2"); fi
export PYTHONPATH=$job/source:$job/source/src
export PYTHONDONTWRITEBYTECODE=1 XDG_CACHE_HOME=$job/cache CUDA_CACHE_PATH=$job/cache/cuda
export TORCH_HOME=$job/cache/torch TRITON_CACHE_DIR=$job/cache/triton TMPDIR=$job/tmp
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1
export EXIT_LOADER_WORKERS=${EXIT_LOADER_WORKERS:-6}
export EXIT_LOADER_AMENDMENT=$job/loader6.json
export EXIT_LOADER_AMENDMENT_SHA256
EXIT_LOADER_AMENDMENT_SHA256=$(sha256sum "$EXIT_LOADER_AMENDMENT" | cut -d ' ' -f 1)
cd "$job/source"
exec "$job/venv/bin/python" -B "$job/ops/fit_runtime.py" \
  --init-checkpoint "$job/inputs/main02.pt" --human-store "$job/human/train" \
  --assets "$job/inputs/assets.npz" --teacher-root "$job/corpus" --teacher-ratio "$ratio" \
  --steps "$steps" --batch-size 8192 --microbatch "$micro" --warmup 2000 --seed 2026101001 \
  --temperature "$temperature" --play-weight 1 --value-weight 0 --checkpoint-every 250 \
  --output "${EXIT_FIT_OUTPUT:-$job/fits/$arm}" --stop "$job/FIT.STOP" "${extra[@]}"
