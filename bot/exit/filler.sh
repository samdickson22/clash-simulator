#!/usr/bin/env bash
# Standing low-priority CPU filler (BOT LEAD 2026-10-17): keeps a host near TARGET live python with short niced blocks
# that yield to real jobs. One filler per host, detached:
#   bot/detach.sh STATE/filler.log STATE/filler.receipt.json bot/exit/filler.sh STATE [TARGET=95] [CAP=105]
# STATE/queue: one block per line, "<workers> <group> <shell command>" (the command cds into its own tree). Every 30 s:
# if no other job is waiting for admission (claim files), the next line's group has no live block, and
# live python + leased-idle room + workers + 1 <= TARGET (< CAP; CLAIMS/max-live - 4 if lower), launch it detached as
#   bot/exit/cpu_job.sh <workers+1> nice -n 19 bash -c <command>
# so it holds a normal lease (real jobs see it) and runs at the lowest priority. Blocks of one group run one at a
# time (e.g. one K1 shard's output dir). Position persists in STATE/next; append lines to extend the queue; STATE/STOP
# stops launching (running blocks finish). Each launch is logged with the counts it saw.
set -uo pipefail
export NUMPY_MADVISE_HUGEPAGE=0
state=${1:?STATE}; target=${2:-95}; cap=${3:-105}
(( target < cap )) || { echo 'TARGET must be below CAP' >&2; exit 1; }
repo=$(cd "$(dirname "$0")/../.." && pwd); claims=/mpac/sdicks02/jobs/clasher/bot-cpu-claims
mkdir -p "$state/blocks"; [[ -s "$state/next" ]] || echo 1 > "$state/next"
log() { echo "$(date -u +%FT%TZ) $*"; }
live_py() { ps -u "$USER" -o stat=,args= | grep -v '^Z' | grep '[p]ython' | grep -Evc "${BOT_CPU_IGNORE:-train_cr\.py}"; }
leased_idle() {   # cpu_room.sh's rule: each lease's process group at its largest N, minus its live python
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
waiting() { local f t=0; for f in "$claims"/claim-*; do [[ -e "$f" ]] && kill -0 "${f##*claim-}" 2>/dev/null && t=$((t+1)); done; echo "$t"; }
group_live() { local r; for r in "$state"/blocks/*-"$1".receipt.json; do [[ -e "$r" ]] || continue
    kill -0 "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['pgid'])" "$r")" 2>/dev/null && return 0; done; return 1; }
log "filler start host $(hostname) target $target cap $cap repo $repo"
while [[ ! -e "$state/STOP" ]]; do
    i=$(cat "$state/next"); line=$(sed -n "${i}p" "$state/queue" 2>/dev/null)
    if [[ -z "$line" ]]; then sleep 60; continue; fi
    read -r w grp cmd <<< "$line"
    if ! [[ "$w" =~ ^[0-9]+$ ]] || (( w < 1 || w > 12 )) || [[ -z "$cmd" ]]; then log "bad line $i: $line"; echo $((i+1)) > "$state/next"; continue; fi
    q=$(waiting); p=$(live_py); c=$(leased_idle); eff=$target
    hc=$(cat "$claims/max-live" 2>/dev/null || true)   # per-host ceiling (cpu_room.sh) lowers the target too
    [[ "$hc" =~ ^[0-9]+$ ]] && (( hc - 4 < eff )) && eff=$(( hc - 4 ))
    if (( q == 0 )) && ! group_live "$grp" && (( p + c + w + 1 <= eff )); then
        echo $((i+1)) > "$state/next"
        "$repo/bot/detach.sh" "$state/blocks/$i-$grp.log" "$state/blocks/$i-$grp.receipt.json" \
            "$repo/bot/exit/cpu_job.sh" $((w + 1)) nice -n 19 bash -c "$cmd" > /dev/null
        log "launched block $i group $grp workers $w (live py $p, leased idle $c, waiting 0, target $eff)"
        sleep 45   # let the block start before counting again
        continue
    fi
    sleep 30
done
log "STOP present; filler exits (running blocks continue)"
