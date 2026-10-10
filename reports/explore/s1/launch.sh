#!/usr/bin/env bash
set -euo pipefail
job=${S1_JOB:-/mpac/sdicks02/jobs/clasher/s1-20261010-r1}
phase=${1:?smoke/reporting}
test -s "$job/QUALIFIED"
test -s "$job/BELIEF-QUALIFIED"
test -s "$job/TESTS-PASS"
test -s "$job/runtime-pin.json"
test -s "$job/R3-RELEASE-ADMITTED.json"
if [[ "$phase" == reporting ]]; then test -s "$job/SMOKE-PASS"; fi
mkdir "$job/$phase-launch-claim"
bash "$job/repo/reports/explore/s1/detach.sh" "$job/$phase-supervisor.log" "$job/$phase-supervisor-pid.json" nice -n 10 taskset -c 39 bash "$job/repo/reports/explore/s1/runtime.sh" reports/explore/s1/supervise.py --job "$job" --phase "$phase"
