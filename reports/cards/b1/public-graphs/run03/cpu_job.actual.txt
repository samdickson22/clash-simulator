#!/usr/bin/env bash
# Run CMD once the host has room for N python processes (bot/exit/cpu_room.sh), holding a lease for N while it runs
# so cpu_feeder.sh keeps that room free (also across gaps between CMD's phases).
#   bot/exit/cpu_job.sh N CMD...
# Admission (room check + lease write) is atomic under a flock, so two jobs admitted at once cannot both take the same
# room (03, 2026-10-16: 110 live). The lock is held only for one check, never while waiting, so a large job that does
# not fit cannot block smaller ones that do (08, 2026-10-16). While waiting, claim-<pid> keeps cpu_feeder.sh off that room.
# Launch each job in its own session (bot/detach.sh): leases are counted per process group, at the largest N in it.
set -uo pipefail
n=${1:?N}; shift
claims=/mpac/sdicks02/jobs/clasher/bot-cpu-claims; mkdir -p "$claims"
lease=$claims/lease-$$; claim=$claims/claim-$$
trap 'rm -f "$lease" "$claim"' EXIT
echo "$n" > "$claim"
while :; do
    exec 9>"$claims/.admit.lock"; flock 9
    if BOT_CPU_TRY=1 "$(dirname "$0")/cpu_room.sh" "$n"; then
        echo "$n $(ps -o pgid= -p $$ | tr -d ' ')" > "$lease"; rm -f "$claim"
        flock -u 9; exec 9>&-; break
    fi
    flock -u 9; exec 9>&-; sleep 20
done
"$@"
