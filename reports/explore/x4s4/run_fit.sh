#!/usr/bin/env bash
# X4S-4 (exploration, NEVER ADOPTABLE) student fit, copied from X4S-3 run_fit.sh: the R3a recipe of
# exit-r3/operations/run_fit.sh (freeze bc542da8) with only corpus list, train seed,
# steps and paths changed. Usage: run_fit.sh ID [RESUME_CHECKPOINT]
set -euo pipefail
id=${1:?}
J=/mpac/sdicks02/jobs/clasher/x4s4-onpolicy
R1=/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1
extra=()
case "$id" in
  R5)     steps=2500; seed=2026101301; set=onpolicy;   gate=O-VERIFIED.json ;;
  R5-rep) steps=2500; seed=2026101302; set=onpolicy;   gate=O-VERIFIED.json ;;
  R5W)    steps=2500; seed=2026101303; set=onpolicy-w; gate=OW-VERIFIED.json ;;
  *) exit 2 ;;
esac
# r1 plus the verified set (O for R5/R5-rep, O_W for R5W), each packed batch listed x4 (pre-declared
# up-weighting; the trainer samples rows uniformly across listed shards).
[[ -s $J/data/$gate ]]
# Sol r1 F5: command substitution (not process substitution), so a failing producer aborts the script.
listing=$(python3 -c 'import json,sys;print("\n".join(b["name"] for b in json.load(open(sys.argv[1]))["batches"]))' "$J/data/$gate") \
  || { echo "run_fit.sh: cannot read the batch list of $gate" >&2; exit 3; }
mapfile -t batches <<<"$listing"
(( ${#batches[@]} >= 1 && ${#batches[@]} <= 15 ))
for rep in 1 2 3 4; do
  for b in "${batches[@]}"; do
    [[ $b =~ ^batch-[0-9]{4}$ ]]
    extra+=(--extra-teacher-root "$J/data/$set/$b")
  done
done
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
