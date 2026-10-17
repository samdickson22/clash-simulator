#!/usr/bin/env bash
# cards/belief-robust positive smoke on 04/08 (bundle env, live16402b-r3). Args: snapshot outdir player [prior fullpool|c56]
set -euo pipefail
repo=$(realpath "${1:?snapshot}"); out=$(realpath -m "${2:?out}"); player=${3:-LIVE-K4CW-r16}; prior=${4:-fullpool}; mkdir -p "$out"
F=/mpac/sdicks02/jobs/clasher/bot-fullpool
export PYTHONHASHSEED=0 NUMPY_MADVISE_HUGEPAGE=0 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1
export NUMBA_CACHE_DIR=/mpac/sdicks02/jobs/clasher/cards/belief-robust/numba-cache; mkdir -p "$NUMBA_CACHE_DIR"
export CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3
export CLASHER_DELAY_NATIVE_DIR=$CLASHER_BOT_RUNTIME/native CLASHER_BOT_RUNTIME_PINS=live16402b-r3
export CLASHER_LOPP_MODELS=$F/lopp-fp BOT_FULLPOOL_POLICIES=v1=$F/ext/main02-fp.pt,R3a=$F/ext/R3a-fp.pt
export BOT_BELIEF_PRIOR=fullpool:11433651:freq=b53b02a1fde4 CLASHER_LIVE_FAST=student:$F/fits/f1a2/step-001200.pt
unset BOT_CYCLE_MODEL
cd "$repo"
tag=$(echo "$player-$prior" | tr -c 'A-Za-z0-9\n-' _)
PYTHONPATH=. nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B reports/cards/belief-robust/smoke.py \
  "$out/smoke-$tag.json" "$player" "$prior" > "$out/smoke-$tag.log" 2>&1; echo "smoke rc $?" >> "$out/smoke-$tag.log"
