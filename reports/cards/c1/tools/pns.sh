#!/bin/bash
# usage: pns.sh ROOT NATIVE_DIR OUT.json CARD... | --cases   (native==Python lockstep on fidelity scenarios)
set -u
J=/mpac/sdicks02/jobs/clasher/cards/c1
root=$(readlink -f $1); nat=$(readlink -f $2); out=$(readlink -f $3); shift 3
cd $root
export PYTHONPATH=$nat:engine-rs:src:/mpac/sdicks02/repos/clasher-bot-runtime/r1/reports/strategy_council_20260928/engine-speed CARDS_GAMEDATA=$root/gamedata.json OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONHASHSEED=0
exec nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B $J/fid/probe_native_scen.py $out "$@"
