#!/bin/bash
set -uo pipefail
cd /Users/sam/Desktop/code/clasher
export ANDROID_ADB_SERVER_PORT=5042 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
label=$1; shift
printf 'v4 %s PID %s starting\n' "$label" "$$"
nice -n 10 "$@"
status=$?
printf '%s\n' "$status" > "reports/strategy_council_20260928/live-loop/v4/$label.exit"
exit "$status"
