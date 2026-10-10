#!/usr/bin/env bash
set -euo pipefail
job=${T1_JOB:-/mpac/sdicks02/jobs/clasher/t1-20261010-r1}
phase=${1:?smoke/reporting/replacement}
dispatch=${2:?frozen dispatch JSON}
attempt=${3:-}
case "$phase" in smoke|reporting|replacement|corpus) ;; *) exit 2 ;; esac
test -s "$job/runtime-pin.json"
if [[ "$phase" != smoke && "$phase" != corpus ]]; then
    test -s "$job/FROZEN-T1.json"
    test -s "$job/REPORTING-AUTHORIZATION.json"
    test -s "$job/SMOKE-PASS"
fi
extra=()
namespace=$phase
if [[ "$phase" == replacement ]]; then
    [[ "$attempt" =~ ^r[0-9]+$ ]]
    extra=(--attempt "$attempt")
    namespace=$phase-$attempt
fi
bash "$job/repo/reports/explore/t1/detach.sh" "$job/$namespace-supervisor.log" "$job/$namespace-supervisor-pid.json" nice -n 10 taskset -c 61 bash "$job/repo/reports/explore/t1/runtime.sh" reports/explore/t1/supervise.py --job "$job" --phase "$phase" --dispatch "$dispatch" "${extra[@]}"
