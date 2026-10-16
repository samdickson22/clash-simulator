#!/usr/bin/env bash
# Run CMD once the host has room for N python processes (bot/exit/cpu_room.sh), holding a lease for N while it runs
# so cpu_feeder.sh keeps that room free (also across gaps between CMD's phases).
#   bot/exit/cpu_job.sh N CMD...
# Admission (room check + lease write) is serialised with flock, so two jobs admitted at once cannot both see the same
# room before either has started its processes (03, 2026-10-16: 110 live from two concurrent admissions). Launch each
# job in its own session (bot/detach.sh): leases are counted per process group, at the largest N in that group.
set -uo pipefail
n=${1:?N}; shift
claims=/mpac/sdicks02/jobs/clasher/bot-cpu-claims; mkdir -p "$claims"
exec 9>"$claims/.admit.lock"; flock 9
"$(dirname "$0")/cpu_room.sh" "$n"
lease=$claims/lease-$$
echo "$n $(ps -o pgid= -p $$ | tr -d ' ')" > "$lease"; trap 'rm -f "$lease"' EXIT
flock -u 9; exec 9>&-
"$@"
