#!/usr/bin/env bash
# DECK SEARCH v3 launcher: bash run.sh WORKERS DRIVER-ARGS...  (env as live-diag's PEKKA-1 run-l16-cadence.sh)
set -euo pipefail
workers=${1:?workers}; shift
job=/mpac/sdicks02/jobs/clasher/bot-deckopt3
code=$job/code
source_tree=/mpac/sdicks02/repos/clasher-bot-livediag-par-7df775763   # PEKKA-1's tree (git archive of main 7df775763)
case "$(hostname -s)" in
 127x04) old=/mpac/sdicks02/jobs/clasher/bot-deckopt2; helpers=/mpac/sdicks02/jobs/clasher/bot-deckopt2-sam
         runtime_root=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3 ;;
 127x08) old=/mpac/sdicks02/jobs/clasher/bot-livediag/mirror/bot-deckopt2; helpers=/mpac/sdicks02/jobs/clasher/bot-livediag/mirror/bot-deckopt2-sam
         runtime_root=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3 ;;
 *) echo "unsupported host" >&2; exit 2 ;;
esac
export LIVEDIAG_OLD=$old
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT BOT_BELIEF_PRIOR CLASHER_LIVE_FAST
export NUMBA_CACHE_DIR=$job/numba-cache
export PYTHONHASHSEED=0 NUMPY_MADVISE_HUGEPAGE=0 PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1
export CLASHER_BOT_RUNTIME="$runtime_root" CLASHER_DELAY_NATIVE_DIR="$runtime_root/native" CLASHER_BOT_RUNTIME_PINS=live16402b-r3
export CLASHER_LOPP_MODELS="$old/fullpool/models/lopp-fp"
export BOT_FULLPOOL_POLICIES="v1=$old/fullpool/models/ext/main02-fp.pt,R3a=$old/fullpool/models/ext/R3a-fp.pt"
export CLASHER_LEVELS_PLACEMENT_PROOF="$old/placement-proof.json"
export PYTHONPATH="$code:$helpers:$old:$source_tree"
mkdir -p "$NUMBA_CACHE_DIR"
cd "$source_tree"
date -u
who
[[ -n ${DECKOPT3_PLAN:-} ]] && exec /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -m deckopt3_driver --plan --workers "$workers" "$@"   # bank only, no game
exec /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh "$((workers+2))" nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -m deckopt3_driver --workers "$workers" "$@"
