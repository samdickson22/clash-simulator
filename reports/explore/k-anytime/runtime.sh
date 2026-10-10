#!/usr/bin/env bash
set -euo pipefail
job=${K_JOB:-/mpac/sdicks02/jobs/clasher/k-anytime-20261010-r1}
repo=$job/repo
py=/mpac/sdicks02/repos/clasher/.venv/bin/python
export CUDA_VISIBLE_DEVICES='' PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1
export XDG_CACHE_HOME=$job/cache PYTHONPYCACHEPREFIX=$job/cache/pycache NUMBA_CACHE_DIR=$job/cache/numba
export CLASHER_DELAY_NATIVE_DIR=$job/native CLASHER_ROOT=$repo CLASHER_EVAL_RUNTIME_ROOT=$repo
export PYTHONPATH=$repo:$CLASHER_DELAY_NATIVE_DIR:$repo/src:$repo/engine-rs:$repo/reports/explore/k-anytime:$repo/reports/explore/e1:$repo/reports/strategy_council_20260928/engine-speed/stage5:$repo/reports/strategy_council_20260928/engine-speed:$repo/reports/strategy_council_20260928/search-noise-s6:$repo/reports/strategy_council_20260928/search-noise-s4:$repo/reports/perf-audit/quickwins
cd "$repo"
exec "$py" -B "$@"
