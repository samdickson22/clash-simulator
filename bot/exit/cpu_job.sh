#!/usr/bin/env bash
# Run CMD once the host has room for N python processes (bot/exit/cpu_room.sh), holding a lease for N while it runs
# so cpu_feeder.sh keeps that room free (also across gaps between CMD's phases).
#   bot/exit/cpu_job.sh N CMD...
set -uo pipefail
n=${1:?N}; shift
"$(dirname "$0")/cpu_room.sh" "$n"
lease=/mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-$$
echo "$n $(ps -o pgid= -p $$ | tr -d ' ')" > "$lease"; trap 'rm -f "$lease"' EXIT
"$@"
