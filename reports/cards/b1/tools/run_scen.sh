#!/bin/bash
# usage (08, from b1/fid): run_scen.sh ROOTNAME NATIVEDIR OUT CARD...   native==Python lockstep on the fidelity scenarios
B=/mpac/sdicks02/jobs/clasher/cards/b1; R1=/mpac/sdicks02/repos/clasher-bot-runtime/r1
root=$1; nat=$2; out=$3; shift 3
cd $B/fid
CLASHER_ROOT=$B/$root PYTHONPATH=$nat:$B/$root/engine-rs:$B/$root/src:$R1/reports/strategy_council_20260928/engine-speed PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
  exec nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B probe_native_scen.py $out "$@"
