#!/usr/bin/env bash
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/bot-deckopt2-levelgain-20261017
old=/mpac/sdicks02/jobs/clasher/bot-deckopt2
label=${1:?label}; workers=${2:?workers}; shift 2
case "$(hostname -s)" in
 127x01) root=/mpac/sdicks02/jobs/clasher/bot-fullpool/roots/live16402b-r3 ;;
 127x03|127x04) root=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3 ;;
 *) exit 2 ;;
esac
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT BOT_BELIEF_PRIOR CLASHER_LIVE_FAST
export PYTHONHASHSEED=0 NUMPY_MADVISE_HUGEPAGE=0 PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1
export NUMBA_CACHE_DIR="$job/numba-cache"
mkdir -p "$NUMBA_CACHE_DIR"
export CLASHER_BOT_RUNTIME="$root" CLASHER_DELAY_NATIVE_DIR="$root/native" CLASHER_BOT_RUNTIME_PINS=live16402b-r3
export CLASHER_LOPP_MODELS="$old/fullpool/models/lopp-fp"
export BOT_FULLPOOL_POLICIES="v1=$old/fullpool/models/ext/main02-fp.pt,R3a=$old/fullpool/models/ext/R3a-fp.pt"
export CLASHER_LEVELS_PLACEMENT_PROOF="$old/placement-proof.json"
export PYTHONPATH="$job:$old:/mpac/sdicks02/repos/clasher-bot-deckopt2-fullpool"
cd /mpac/sdicks02/repos/clasher-bot-deckopt2-fullpool
date -u
who
exec /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh "$((workers+2))" nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python "$job/extended_worker.py" --label "$label" --workers "$workers" "$@"
