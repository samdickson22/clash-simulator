#!/usr/bin/env bash
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -euo pipefail
source_tree=${1:?isolated source checkout containing the reviewed RoyaleSim noise hook}
workers=${2:?workers}; shift 2
helpers=/mpac/sdicks02/jobs/clasher/bot-deckopt2-sam
mine=/mpac/sdicks02/jobs/clasher/bot-livediag/cadence
old=/mpac/sdicks02/jobs/clasher/bot-deckopt2
case "$(hostname -s)" in
 127x01) runtime_root=/mpac/sdicks02/jobs/clasher/bot-fullpool/roots/live16402b-r3 ;;
 127x03|127x04) runtime_root=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3 ;;
 *) exit 2 ;;
esac
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT BOT_BELIEF_PRIOR CLASHER_LIVE_FAST
export NUMBA_CACHE_DIR=/mpac/sdicks02/cache/numba-livediag
export PYTHONHASHSEED=0 NUMPY_MADVISE_HUGEPAGE=0 PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1
export CLASHER_BOT_RUNTIME="$runtime_root" CLASHER_DELAY_NATIVE_DIR="$runtime_root/native" CLASHER_BOT_RUNTIME_PINS=live16402b-r3
export CLASHER_LOPP_MODELS="$old/fullpool/models/lopp-fp"
export BOT_FULLPOOL_POLICIES="v1=$old/fullpool/models/ext/main02-fp.pt,R3a=$old/fullpool/models/ext/R3a-fp.pt"
export CLASHER_LEVELS_PLACEMENT_PROOF="$old/placement-proof.json"
export PYTHONPATH="$mine:$helpers:$old:$source_tree"
cd "$source_tree"
date -u
who
exec /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh "$((workers+2))" nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -m l16_cadence --workers "$workers" "$@"
