#!/usr/bin/env bash
set -euo pipefail
job=${KV2_JOB:-/mpac/sdicks02/jobs/clasher/k-v2-20261010-r1}
phase=${1:?smoke/reporting}
test -s "$job/QUALIFIED"
if [[ "$phase" == reporting ]]; then test -s "$job/SMOKE-PASS"; fi
mkdir "$job/$phase-launch-claim"
bash "$job/repo/reports/explore/k-v2/detach.sh" "$job/$phase-supervisor.log" "$job/$phase-supervisor-pid.json" nice -n 10 taskset -c 45 bash "$job/repo/reports/explore/k-v2/runtime.sh" reports/explore/k-v2/supervise.py --job "$job" --phase "$phase"
