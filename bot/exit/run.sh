#!/usr/bin/env bash
# Multi-process CPU launcher for bot.exit / bot.eval (nice 19, 1 thread per process, no GPU).
#   bot/exit/run.sh -m bot.exit.generate --out DIR ...
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -euo pipefail
export NUMPY_MADVISE_HUGEPAGE=0  # no THP madvise: direct compaction stalls numpy allocs 2-47 s on fragmented hosts (LIVE LEAD 10-15)
repo=$(cd "$(dirname "$0")/../.." && pwd)
export CLASHER_BOT_RUNTIME=${CLASHER_BOT_RUNTIME:-/mpac/sdicks02/repos/clasher-bot-runtime/r1}
export CUDA_VISIBLE_DEVICES='' PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
cd "$repo"
exec nice -n 19 "$repo/.venv/bin/python" -B "$@"
