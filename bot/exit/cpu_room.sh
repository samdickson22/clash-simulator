#!/usr/bin/env bash
# Block until this host has room for N more python processes under CAP live (non-zombie) python processes of $USER.
#   bot/exit/cpu_room.sh N [CAP=${BOT_CPU_CAP:-105}]   (CLAIMS/max-live, if present, lowers CAP)
# Room also excludes what running jobs have leased but are not using right now (CLAIMS/lease-<pid> "N pgid", each
# process group counted once at its largest N), so a job in a gap between phases is not stacked on (08, 21:55Z).
# While waiting it holds a claim (CLAIMS/claim-<pid> containing N) that cpu_feeder.sh subtracts from its room, so
# the feeder cannot starve the waiting job.
n=${1:?N}; cap=${2:-${BOT_CPU_CAP:-105}}; claims=/mpac/sdicks02/jobs/clasher/bot-cpu-claims
# per-host ceiling (e.g. 89 on 01 while the LIVE LEAD holds 16 loader cores): CLAIMS/max-live lowers CAP
hostcap=$(cat "$claims/max-live" 2>/dev/null || true); [[ "$hostcap" =~ ^[0-9]+$ ]] && (( hostcap < cap )) && cap=$hostcap
mkdir -p "$claims"; echo "$n" > "$claims/claim-$$"; trap 'rm -f "$claims/claim-$$"' EXIT
# python processes that don't compete for these cores (the LIVE LEAD's YOLO dataloaders) are not counted
live() { ps -u "$USER" -o stat=,args= | grep -v '^Z' | grep '[p]ython' | grep -Evc "${BOT_CPU_IGNORE:-train_cr\.py}"; }
leased_idle() {
    local -A want=(); local f k g t=0 used
    for f in "$claims"/lease-*; do
        [[ -e "$f" ]] && kill -0 "${f##*lease-}" 2>/dev/null || continue
        read -r k g < "$f"; [[ -n "$g" ]] || continue
        (( k > ${want[$g]:-0} )) && want[$g]=$k
    done
    for g in "${!want[@]}"; do
        used=$(ps -u "$USER" -o pgid=,stat=,args= | awk -v g="$g" '$1 == g && $2 !~ /^Z/ && /[p]ython/' | wc -l)
        (( want[$g] > used )) && t=$(( t + want[$g] - used ))
    done; echo "$t"; }
while (( $(live) + $(leased_idle) + n > cap )); do sleep 20; done
