#!/usr/bin/env bash
# X4S-3 (exploration, NEVER ADOPTABLE) student fit: the R3a recipe of
# exit-r3/operations/run_fit.sh (freeze bc542da8) with only corpus list, train seed,
# steps and paths changed. Usage: run_fit.sh ID [RESUME_CHECKPOINT]
set -euo pipefail
id=${1:?}
J=/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012
R1=/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1
extra=()
case "$id" in
  R3a-rep) steps=2500; seed=2026101202 ;;
  R4-D)    steps=2500; seed=2026101201 ;;
  R4-DC)   steps=5000; seed=2026101203 ;;
  *) exit 2 ;;
esac
if [[ $id == R4-* ]]; then
  [[ -s $J/data/G-UNION-VERIFIED.json ]]
  for d in "$J"/data/g01/batch-000{00,01} "$J"/data/g08/batch-000{00,01,02,03,04,05,06,07,08,09,10}; do
    extra+=(--extra-teacher-root "$d")
  done
fi
if [[ -n ${2:-} ]]; then extra+=(--resume "$2"); fi
# Operational only: the 14-shard union keeps ~1,000 mmapped arrays open (R3's 6 shards stayed under the
# default soft limit of 1024). Raise the soft nofile limit within the hard limit.
ulimit -Sn 65536
export PYTHONPATH=$J/fit/source:$J/fit/source/src PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME=$J/cache/fit CUDA_CACHE_PATH=$J/cache/fit/cuda TORCH_HOME=$J/cache/fit/torch
export TRITON_CACHE_DIR=$J/cache/fit/triton TMPDIR=$J/cache/fit/tmp
mkdir -p "$TMPDIR"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1
export EXIT_LOADER_WORKERS=6 EXIT_LOADER_AMENDMENT=$J/fit/loader6.json
export EXIT_LOADER_AMENDMENT_SHA256
EXIT_LOADER_AMENDMENT_SHA256=$(sha256sum "$EXIT_LOADER_AMENDMENT" | cut -d ' ' -f 1)
cd "$J/fit/source"
exec /mpac/sdicks02/envs/clasher-gpu/bin/python -B "$J/fit/ops/fit_runtime.py" \
 --init-checkpoint "$J/inputs/main02.pt" --human-store "$R1/human/train" \
 --assets "$J/inputs/assets.npz" --teacher-root "$R1/corpus" --teacher-ratio 1 \
 "${extra[@]}" \
 --steps "$steps" --batch-size 8192 --microbatch 3584 --warmup 2000 --seed "$seed" \
 --temperature .003 --play-weight 1 --value-weight 0 --advantage-weight 0 \
 --checkpoint-every 250 --output "$J/fits/$id" --stop "$J/FIT.STOP"
