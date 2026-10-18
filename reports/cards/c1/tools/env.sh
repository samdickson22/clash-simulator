# source: PYTHONPATH for probes on 04 (native dir $NAT, root $ROOT)
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
J=/mpac/sdicks02/jobs/clasher/cards/c1
export PYTHONPATH=$NAT:$ROOT/engine-rs:$ROOT/src:/mpac/sdicks02/repos/clasher-bot-runtime/r1/reports/strategy_council_20260928/engine-speed:$J/tools:$J/ctools
export CARDS_GAMEDATA=$ROOT/gamedata.json PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
