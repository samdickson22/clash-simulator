#!/bin/bash
# Usage: run_capture.sh INDEX [OPPONENT] -- one captured K4C-r16 game on 127x03.
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -euo pipefail
cd /mpac/sdicks02/repos/clasher-bot
export ROYALEGYM_SRC=/mpac/sdicks02/repos/clasher-bot-rsim/upstream/RoyaleGym/royalegym
export CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
exec nice -n 10 .venv/bin/python -B /mpac/sdicks02/jobs/clasher/bot-preview/code/capture.py --index "$1" --opponent "${2:-v1}" --out /mpac/sdicks02/jobs/clasher/bot-preview/captures
