#!/usr/bin/env bash
# cards/belief-robust default-off parity arm (fixed timing; run on 08 under bot/exit/cpu_job.sh 4).
# Args: source snapshot, output dir. Rows: K4L-R-gs-rw-fc HEADLINE 0-5 x R3a,v1 (C56 prior, live16402c, the
# fullscope-belief gate), LIVE-K4CW-r16 HEADLINE 0-2 x R3a (C56 LiveBelief), then full-pool res_check LIVE-AB1 0-3 for
# K4L-R-gs-mk1a1 and LIVE-K4CW-r16 (BUNDLE env, live16402b-r3, FullPoolBelief).
set -euo pipefail
repo=$(realpath "${1:?snapshot}"); out=$(realpath -m "${2:?output}"); mkdir -p "$out"
py=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
export PYTHONHASHSEED=0 NUMPY_MADVISE_HUGEPAGE=0 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
export NUMBA_CACHE_DIR=/mpac/sdicks02/jobs/clasher/cards/belief-robust/numba-cache; mkdir -p "$NUMBA_CACHE_DIR"
cd "$repo"
(
  export CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/live16402c
  export CLASHER_DELAY_NATIVE_DIR=$CLASHER_BOT_RUNTIME/native CLASHER_BOT_RUNTIME_PINS=live16402c
  unset BOT_BELIEF_PRIOR BOT_CYCLE_MODEL BOT_FULLPOOL_POLICIES CLASHER_LIVE_FAST CLASHER_LOPP_MODELS
  nice -n 15 "$py" -B -m bot.eval.headline --out "$out/k4l" --candidate K4L-R-gs-rw-fc \
    --opponents R3a,v1 --games 6 --workers 3 > "$out/k4l.log" 2>&1
  nice -n 15 "$py" -B -m bot.eval.headline --out "$out/k4cw" --candidate LIVE-K4CW-r16 \
    --opponents R3a --games 3 --workers 3 > "$out/k4cw.log" 2>&1
)
(
  F=/mpac/sdicks02/jobs/clasher/bot-fullpool
  export CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3
  export CLASHER_DELAY_NATIVE_DIR=$CLASHER_BOT_RUNTIME/native CLASHER_BOT_RUNTIME_PINS=live16402b-r3
  export CLASHER_LOPP_MODELS=$F/lopp-fp BOT_FULLPOOL_POLICIES=v1=$F/ext/main02-fp.pt,R3a=$F/ext/R3a-fp.pt
  export BOT_BELIEF_PRIOR=fullpool:11433651:freq=b53b02a1fde4 CLASHER_LIVE_FAST=student:$F/fits/f1a2/step-001200.pt
  unset BOT_CYCLE_MODEL
  nice -n 15 "$py" -B -m bot.fullpool.res_check "$out/fp.jsonl" --names K4L-R-gs-mk1a1,LIVE-K4CW-r16 \
    --cases 0-3 --procs 3 > "$out/fp.log" 2>&1
)
echo GATE_DONE
