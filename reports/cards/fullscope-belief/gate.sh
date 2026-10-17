#!/usr/bin/env bash
# Run on 04/08 under /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 4.
# Args: source snapshot, output directory, belief (unset or c56).
set -euo pipefail
repo=${1:?source snapshot}; out=${2:?output}; prior=${3:-unset}
export PYTHONHASHSEED=0 NUMPY_MADVISE_HUGEPAGE=0 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
export CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/live16402c
export CLASHER_DELAY_NATIVE_DIR=$CLASHER_BOT_RUNTIME/native CLASHER_BOT_RUNTIME_PINS=live16402c
export NUMBA_CACHE_DIR=/mpac/sdicks02/jobs/clasher/cards/fullscope-belief/numba-cache
unset BOT_BELIEF_PRIOR BOT_CYCLE_MODEL BOT_FULLPOOL_POLICIES CLASHER_LIVE_FAST CLASHER_LOPP_MODELS
if [[ "$prior" != unset ]]; then export BOT_BELIEF_PRIOR=$prior; fi
mkdir -p "$out" "$NUMBA_CACHE_DIR"
repo=$(realpath "$repo"); out=$(realpath "$out")
cd "$repo"
py=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
# Serial fc scorer: three workers plus headline controller fit the four-process lease.
nice -n 15 "$py" -B -m bot.eval.headline --out "$out/k4l" --candidate K4L-R-gs-rw-fc \
  --opponents R3a,v1 --games 6 --workers 3 > "$out/k4l.log" 2>&1
nice -n 15 "$py" -B -m bot.eval.headline --out "$out/k4cw" --candidate K4CW-r16 \
  --opponents R3a --games 1 --workers 1 > "$out/k4cw.log" 2>&1
