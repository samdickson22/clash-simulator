#!/usr/bin/env bash
# HP1 S0 environment (reports/bot/hp1/S0-PREREG.md). Mirrors NS2's env.sh; host 04.
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/bot-hp1-s0-20261017
cd "$job/source"
export PYTHONPATH="$job/source"
ROOT=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3
PINS=live16402b-r3
NUMBA_CACHE_DIR=$job/numba-cache
source bot/fullpool/run/env.sh
export BOT_BELIEF_PRIOR=fullpool:11433651:freq=b53b02a1fde4
export CLASHER_LIVE_FAST=student:/mpac/sdicks02/jobs/clasher/bot-fullpool/ext/policy-00010.pt@0.5375
export REXT_EXT2_MODELS=/mpac/sdicks02/jobs/clasher/bot-ext2-models
export PYTHONHASHSEED=0 NUMPY_MADVISE_HUGEPAGE=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 TORCH_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 BOT_CPU_CAP=70 BOT_PLAYLOG=1
unset BOT_CYCLE_MODEL BOT_LEAF_VALUE
py=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
BASE=1192128049223264          # screen bank (cases 0-99 scored, 100-101 smoke)
CALBASE=874184153281168        # TRAIN1
CALSTART=46359089              # 64 calibration cases, same every round
V2=$job/models/v2-best-dev-step-00046459.pt
F1A2=student:$job/models/f1a2-step-001200.pt@0.5375
