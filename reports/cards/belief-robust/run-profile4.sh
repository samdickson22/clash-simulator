#!/usr/bin/env bash
# Twin of bot-livediag tail/run-profile.sh (same env) with a 4-process cpu_job lease (cards/belief-robust gates).
set -euo pipefail
OUT=${1:?out json}; PLAYER=${2:?player}; shift 2
L=/mpac/sdicks02/jobs/clasher/bot-livediag; B=$L/fpbench; M=/mpac/sdicks02/jobs/clasher/bot-deckopt2/fullpool/models
RT=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3; CODE=${CODE:?CODE tree}
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT LL_PINS
export PYTHONPATH=$CODE:$CODE/src:$CODE/live/perception CLASHER_BOT_RUNTIME=$RT CLASHER_DELAY_NATIVE_DIR=$RT/native \
  CLASHER_BOT_RUNTIME_PINS=live16402b-r3 CLASHER_LIVE_TRUE_IDS=$B/yolo/true-ids-v3b.json \
  CLASHER_LIVE_OWNER_MODEL=$B/yolo/owner-v11/owner.json \
  CLASHER_LIVE_FAST=student:$M/fits/f1a2/step-001200.pt CLASHER_LOPP_MODELS=$M/lopp-fp \
  BOT_FULLPOOL_POLICIES=v1=$M/ext/main02-fp.pt,R3a=$M/ext/R3a-fp.pt \
  BOT_BELIEF_PRIOR=fullpool:11433651:freq=b53b02a1fde4 LL_HANDSYNC=1 \
  PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 NUMPY_MADVISE_HUGEPAGE=0 PYTHONHASHSEED=0 \
  NUMBA_CACHE_DIR=/mpac/sdicks02/cache/numba-livediag CUDA_VISIBLE_DEVICES=
cd /tmp
date -u; who
exec /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 4 nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B $L/tail/tail_profile.py --bench $B/bench8b/fp_mac_bench.py --code "$CODE" --player "$PLAYER" --out "$OUT" "$@"
