#!/usr/bin/env bash
set -euo pipefail
job=${K2_JOB:-/mpac/sdicks02/jobs/clasher/k2-20261010-r1}
phase=${1:?smoke/reporting}
test -s "$job/QUALIFIED"
test -s "$job/BELIEF-QUALIFIED"
test -s "$job/K-V2-RELEASE-ADMITTED.json"
if [[ "$phase" == reporting ]]; then test -s "$job/SMOKE-PASS"; fi
mkdir "$job/$phase-launch-claim"
bash "$job/repo/reports/explore/k2/detach.sh" "$job/$phase-supervisor.log" "$job/$phase-supervisor-pid.json" nice -n 10 taskset -c 59 bash "$job/repo/reports/explore/k2/runtime.sh" reports/explore/k2/supervise.py --job "$job" --phase "$phase"
