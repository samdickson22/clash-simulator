#!/usr/bin/env bash
set -euo pipefail
job=${EXIT_R1_JOB:-/mpac/sdicks02/jobs/clasher/exit-r1-20261009-r1}
repo=$job/source
export CUDA_VISIBLE_DEVICES='' PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1
export XDG_CACHE_HOME=$job/cache PYTHONPYCACHEPREFIX=$job/cache/pycache CLASHER_ROOT=$repo CLASHER_EVAL_RUNTIME_ROOT=$repo
export CLASHER_DELAY_NATIVE_DIR=$job/native
export PYTHONPATH=$repo:$repo/src:$repo/engine-rs:$repo/reports/strategy_council_20260928/engine-speed/stage5:$repo/reports/strategy_council_20260928/engine-speed:$repo/reports/strategy_council_20260928/search-noise-s6
cd "$repo"
case $(hostname) in
  127x03) cores=${EXIT_R1_CORES:-62-127} ;;
  127x04) cores=${EXIT_R1_CORES:-30-127} ;;
  127x08) cores=${EXIT_R1_CORES:-0-125} ;;
  *) echo 'ExIt execution is limited to authorized home hosts' >&2; exit 1 ;;
esac
exec taskset -c "$cores" /mpac/sdicks02/repos/clasher/.venv/bin/python -B "$@"
