#!/bin/bash
# usage: ctl.sh ROOT OUT.jsonl --cards ... [--offsets ...]   (on 127x08 from b2/fid; controlled spell probes, one worker)
root=$(readlink -f "$1"); out=$2; shift 2
cd "$(dirname "$0")"
export CLASHER_ROOT=$root PYTHONPATH=$root/src FIDELITY_EXPECT_SRC=$(readlink -f "$root/src")/ NUMBA_CACHE_DIR=$PWD/numba-cache PYTHONHASHSEED=0
exec nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B controlled.py --out "$out" --workers 1 --table 160402 "$@"
