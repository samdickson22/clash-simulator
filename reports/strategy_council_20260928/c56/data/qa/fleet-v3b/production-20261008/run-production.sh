#!/usr/bin/env bash
# Run on the target compute node. Inspect existing locks/PIDs and exits first.
set -euo pipefail
source /mpac/sdicks02/env.sh
cd /mpac/sdicks02/repos/clasher
D=$PWD/reports/strategy_council_20260928/c56/data
export CLASHER_ROOT=$D/runtime-engine-v3b PYTHONPATH=$D/runtime-engine-v3b/src
export C56_FLEET_Q=$D/qa/fleet-v3b/production-20261008
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mode=${1:?supervise or extract}; label=${2:?fresh job label}; workers=${3:-4}
export C56_JOB_LABEL=$label
if [[ $mode == supervise ]]; then
  [[ $(hostname -s) == 127x01 ]]
  exec bash reports/strategy_council_20260928/fleet/fleet_run.sh "$label" env "CLASHER_ROOT=$CLASHER_ROOT" "PYTHONPATH=$PYTHONPATH" "C56_FLEET_Q=$C56_FLEET_Q" "C56_JOB_LABEL=$C56_JOB_LABEL" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 "$PWD/.venv/bin/python" -B "$D/scripts/fleet_v3b_production_20261008.py" supervise
elif [[ $mode == extract ]]; then
  exec bash reports/strategy_council_20260928/fleet/fleet_run.sh "$label" env "CLASHER_ROOT=$CLASHER_ROOT" "PYTHONPATH=$PYTHONPATH" "C56_FLEET_Q=$C56_FLEET_Q" "C56_JOB_LABEL=$C56_JOB_LABEL" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 "$PWD/.venv/bin/python" -B "$D/scripts/fleet_v3b_production_worker_20261008.py" extract --workers "$workers"
else
  echo "Invalid mode" >&2; exit 2
fi
