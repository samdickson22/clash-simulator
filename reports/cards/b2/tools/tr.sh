#!/bin/bash
# usage: tr.sh ROOT trace-args...   (on 127x08 from b2/fid; light: one process)
root=$(readlink -f "$1"); shift
cd "$(dirname "$0")"
export CLASHER_ROOT=$root PYTHONPATH=$root/src FIDELITY_EXPECT_SRC=$(readlink -f "$root/src")/ NUMBA_CACHE_DIR=$PWD/numba-cache PYTHONHASHSEED=0
exec nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B trace.py "$@"
