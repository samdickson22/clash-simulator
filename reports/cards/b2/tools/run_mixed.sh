#!/bin/bash
# Run the four native-diff repros on B2, including differential.py's engine-speed dependency.
set -euo pipefail
A=/mpac/sdicks02/jobs/clasher/cards/b2
R1=/mpac/sdicks02/repos/clasher-bot-runtime/r1
cd "$A/root"
export CLASHER_ROOT="$A/root" PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$A/gout:$A/root/engine-rs:$A/root/src:$R1/reports/strategy_council_20260928/engine-speed"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1
exec /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 15 \
  /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B "$A/fid/mixed_repro.py" \
  "$A/fid/nd" "$A/fid/mixed-b2.json" 75 416 133 509
