#!/usr/bin/env bash
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -euo pipefail
export PYTHONHASHSEED=0 NUMPY_MADVISE_HUGEPAGE=0 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=/mpac/sdicks02/jobs/clasher/bot-deckopt2:/mpac/sdicks02/repos/clasher-bot-deckopt2
cd /mpac/sdicks02/repos/clasher-bot-deckopt2
exec nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python /mpac/sdicks02/jobs/clasher/bot-deckopt2/pipeline.py
