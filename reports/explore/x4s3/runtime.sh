#!/usr/bin/env bash
# X4S-3 runtime (from X4S runtime.sh): one runtime copy per student, X4S3_RT=<job>/rt-<ID>.
set -euo pipefail
rt=${X4S3_RT:?}
job=$(dirname "$rt")
repo=$rt/repo
py=/mpac/sdicks02/repos/clasher/.venv/bin/python
export CUDA_VISIBLE_DEVICES='' PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1
export XDG_CACHE_HOME=$job/cache PYTHONPYCACHEPREFIX=$job/cache/pycache NUMBA_CACHE_DIR=$job/cache/numba
export CLASHER_DELAY_NATIVE_DIR=$rt/native CLASHER_ROOT=$repo CLASHER_EVAL_RUNTIME_ROOT=$repo
export PYTHONPATH=$repo:$CLASHER_DELAY_NATIVE_DIR:$repo/src:$repo/engine-rs:$repo/reports/explore/x4s3:$repo/reports/explore/x4s:$repo/reports/explore/s1:$repo/student-source:$repo/reports/explore/e1:$repo/reports/strategy_council_20260928/engine-speed/stage5:$repo/reports/strategy_council_20260928/engine-speed:$repo/reports/strategy_council_20260928/search-noise-s6:$repo/reports/strategy_council_20260928/search-noise-s4:$repo/reports/perf-audit/quickwins
cd "$repo"
exec "$py" -B "$@"
