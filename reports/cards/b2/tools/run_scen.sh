#!/bin/bash
# usage: run_scen.sh ROOTNAME NATIVEDIR OUT CARD...   (127x08, b2/fid; native==Python lockstep per fidelity scenario)
B=/mpac/sdicks02/jobs/clasher/cards/b2; R1=/mpac/sdicks02/repos/clasher-bot-runtime/r1
root=$1 nat=$2 out=$3; shift 3
cd $B/fid
CLASHER_ROOT=$B/$root PYTHONHASHSEED=0 PYTHONPATH=$nat:$B/$root/engine-rs:$B/$root/src:$R1/reports/strategy_council_20260928/engine-speed PYTHONDONTWRITEBYTECODE=1 \
  exec nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B probe_native_scen.py $out "$@"
