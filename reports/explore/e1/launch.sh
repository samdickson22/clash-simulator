#!/usr/bin/env bash
set -euo pipefail
job=${E1_JOB:-/mpac/sdicks02/jobs/clasher/e1-20261009-r1}
phase=${1:?smoke/main/reserve}
workers=${2:-62}
pairs=${3:-600}
offset=${4:-0}
[[ $(hostname -s) == 127x03 || $(hostname -s) == 127x04 || $(hostname -s) == 127x01 ]]
[[ -e "$job/QUALIFIED" ]]
# Never launch a second copy of this phase, including after a lost SSH response.
mkdir "$job/$phase-launch-claim"
setsid nice -n 10 chrt --idle 0 taskset -c "0-$((workers-1))" bash "$job/repo/reports/explore/e1/runtime.sh" reports/explore/e1/supervise.py --job "$job" --phase "$phase" --workers "$workers" --pairs "$pairs" --offset "$offset" > "$job/$phase-supervisor.log" 2>&1 < /dev/null &
printf '%s\n' "$!" > "$job/$phase-supervisor.pid"
cat "$job/$phase-supervisor.pid"
