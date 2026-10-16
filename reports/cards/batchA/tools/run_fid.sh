#!/bin/bash
# usage: run_fid.sh ROOT OUT.jsonl WORKERS [--cards ...]   (run on 127x08 from batchA/fid; baseline: ROOT=../baseroot)
set -euo pipefail
root=$(readlink -f "$1"); out=$2; w=$3; shift 3
cd "$(dirname "$0")"
export CLASHER_ROOT=$root PYTHONPATH=$root/src FIDELITY_EXPECT_SRC=$(readlink -f "$root/src")/ NUMBA_CACHE_DIR=$PWD/numba-cache
exec /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh "$w" nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B scenarios.py --pool pool.json --out "$out" --workers "$w" "$@"
