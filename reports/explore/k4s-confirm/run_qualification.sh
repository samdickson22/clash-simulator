#!/usr/bin/env bash
# PREREG-K4S per-host qualification driver (QUALIFICATION.md steps 3-7), run on the host, detached.
# Usage: K4S_JOB=<staged job> OWNED_STOP=<owned STOP path> NICE=19 bash run_qualification.sh
set -euo pipefail
job=${K4S_JOB:?}; stop=${OWNED_STOP:?}; nice=${NICE:-19}
K=reports/explore/k4s-confirm
cd "$job/repo"
test -L "$job/STOP" && test "$(readlink -f "$job/STOP")" = "$(readlink -f "$stop")"
date -u +%FT%TZ > "$job/QUALIFICATION-STARTED"
nice -n "$nice" bash $K/runtime.sh $K/pin.py --job "$job"
nice -n "$nice" taskset -c 0-4 bash $K/qualify.sh
nice -n "$nice" bash $K/qualify_games.sh
nice -n "$nice" bash $K/runtime.sh $K/stop_test.py --job "$job" --stop "$stop" --cores 5,6,7,8,9
nice -n "$nice" bash $K/runtime.sh $K/make_qualification_receipt.py --job "$job" --out "$job/qualification-$(hostname).json"
date -u +%FT%TZ > "$job/QUALIFICATION-FINISHED"
