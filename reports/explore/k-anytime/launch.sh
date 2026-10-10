#!/usr/bin/env bash
set -euo pipefail
job=${K_JOB:-/mpac/sdicks02/jobs/clasher/k-anytime-20261010-r1}
phase=${1:?smoke/reporting}; pairs=${2:?pairs}; offset=${3:-0}; cpus=${4:?physical cpu count}
mkdir "$job/$phase-launch-claim"
bash "$job/repo/reports/explore/k-anytime/detach.sh" "$job/$phase-supervisor.log" "$job/$phase-supervisor-pid.json" nice -n 10 chrt --idle 0 taskset -c "0-$((cpus-1))" bash "$job/repo/reports/explore/k-anytime/runtime.sh" reports/explore/k-anytime/supervise.py --job "$job" --phase "$phase" --pairs "$pairs" --offset "$offset" --cpus "$cpus"
