#!/usr/bin/env bash
# Standing low-priority CPU filler (BOT LEAD 2026-10-17): keeps a host near TARGET live python with short niced blocks
# that yield to real jobs. One filler per host, detached:
#   bot/detach.sh STATE/filler.log STATE/filler.receipt.json bot/exit/filler.sh STATE [TARGET_LOAD=100] [CAP=112]
# STATE/queue: one block per line, "<workers> <group> <shell command>" (the command cds into its own tree). Every 30 s:
# if no other job is waiting for admission (claim files), take the first unlaunched line (scanning ahead past
# lines whose group already has a live block) and, if 1-min load + workers launched < 90 s ago + workers <= TARGET
# and live python + workers + 1 <= CAP (leased-but-idle room is NOT reserved against filler), launch it detached as
#   BOT_CPU_CAP=1000 bot/exit/cpu_job.sh <workers+1> nice -n 19 bash -c <command>   (lease only; max-live still applies)
# so it holds a normal lease (real jobs see it) and runs at the lowest priority. Blocks of one group run one at a
# time (e.g. one K1 shard's output dir); other groups are not held up. STATE/launched lists launched line numbers and
# STATE/next the first unlaunched one; append lines to extend the queue; STATE/STOP
# stops launching (running blocks finish). Each launch is logged with the counts it saw.
set -uo pipefail
export NUMPY_MADVISE_HUGEPAGE=0
: "${NUMBA_CACHE_DIR:=/mpac/sdicks02/jobs/clasher/bot-fullpool/numba-cache}"; mkdir -p "$NUMBA_CACHE_DIR"; export NUMBA_CACHE_DIR   # roots are read-only, $HOME over quota
state=${1:?STATE}; target=${2:-100}; cap=${3:-112}   # target: 1-min load; cap: hard live-python ceiling
(( target < cap )) || { echo 'TARGET must be below CAP' >&2; exit 1; }
repo=$(cd "$(dirname "$0")/../.." && pwd); claims=/mpac/sdicks02/jobs/clasher/bot-cpu-claims
mkdir -p "$state/blocks"; [[ -s "$state/next" ]] || echo 1 > "$state/next"
log() { echo "$(date -u +%FT%TZ) $*"; }
live_py() { ps -u "$USER" -o stat=,comm=,args= | awk '$1 !~ /^Z/ && $2 ~ /^python/' | grep -Evc "${BOT_CPU_IGNORE:-train_cr\.py}"; }
leased_idle() {   # cpu_room.sh's rule: each lease's process group at its largest N, minus its live python
    local -A want=(); local f k g t=0 used
    for f in "$claims"/lease-*; do
        [[ -e "$f" ]] && kill -0 "${f##*lease-}" 2>/dev/null || continue
        read -r k g < "$f"; [[ -n "$g" ]] || continue
        (( k > ${want[$g]:-0} )) && want[$g]=$k
    done
    for g in "${!want[@]}"; do
        used=$(ps -u "$USER" -o pgid=,stat=,comm= | awk -v g="$g" '$1 == g && $2 !~ /^Z/ && $3 ~ /^python/' | wc -l)
        (( want[$g] > used )) && t=$(( t + want[$g] - used ))
    done; echo "$t"; }
waiting() { local f t=0; for f in "$claims"/claim-*; do [[ -e "$f" ]] && kill -0 "${f##*claim-}" 2>/dev/null && t=$((t+1)); done; echo "$t"; }
live_groups() {   # groups with a live block (receipt pgid alive), one per line
    python3 - "$state/blocks" <<'PY'
import glob, json, os, sys
import time, datetime
now = time.time()
for r in glob.glob(os.path.join(sys.argv[1], '*.receipt.json')):
    g = os.path.basename(r).split('-', 1)[1][:-len('.receipt.json')]
    try:
        rec = json.load(open(r))
        os.kill(rec['pgid'], 0); print(g); continue
    except Exception:
        pass
    # backoff: a block of this group that died with a Traceback within 90 s of its launch, < 10 min ago
    try:
        log = r[:-len('.receipt.json')] + '.log'
        t0 = datetime.datetime.strptime(rec['launched_at_utc'], '%Y-%m-%dT%H:%M:%SZ').replace(
            tzinfo=datetime.timezone.utc).timestamp()
        end = os.path.getmtime(log)
        if end - t0 < 90 and now - end < 600 and 'Traceback' in open(log, errors='replace').read():
            print(g); print('BACKOFF ' + g, file=sys.stderr)
    except Exception:
        pass
PY
}
log "filler start host $(hostname) target $target cap $cap repo $repo"
touch "$state/launched"; recent=()
while [[ ! -e "$state/STOP" ]]; do
    i=$(cat "$state/next")
    while grep -qx "$i" "$state/launched"; do i=$((i+1)); done; echo "$i" > "$state/next"
    if [[ -z "$(sed -n "${i}p" "$state/queue" 2>/dev/null)" ]]; then sleep 60; continue; fi
    q=$(waiting); p=$(live_py); eff=$target; pcap=$cap
    hc=$(cat "$claims/max-live" 2>/dev/null || true)   # per-host python ceiling (cpu_room.sh, e.g. 01 for LIVE loaders)
    [[ "$hc" =~ ^[0-9]+$ ]] && (( hc < pcap )) && pcap=$hc
    # shed: real jobs admitted after filler pushed live python over the cap -> stop the youngest live filler block
    # (one per 60 s) and re-queue its line (RL actor blocks are dropped: their block ids cannot be reused)
    if (( p > pcap + 3 )) && (( $(date +%s) - ${last_shed:-0} >= 60 )); then
        young=$(ls -t "$state"/blocks/*.receipt.json 2>/dev/null | while read -r r; do
            g=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['pgid'])" "$r" 2>/dev/null)
            [[ -n "$g" ]] && kill -0 "$g" 2>/dev/null && { echo "$r $g"; break; }; done)
        if [[ -n "$young" ]]; then
            r=${young% *}; g=${young##* }; b=$(basename "$r"); li=${b%%-*}; line=$(sed -n "${li}p" "$state/queue")
            kill -TERM -"$g" 2>/dev/null; last_shed=$(date +%s)
            read -r w0 g0 c0 <<< "$line"
            [[ "$g0" == rl* ]] || echo "$w0 ${g0} $c0" >> "$state/queue"
            log "shed block $li group $g0 pgid $g (live py $p > cap $pcap + 3); requeued: $([[ "$g0" == rl* ]] && echo no || echo yes)"
        fi
        sleep 30; continue
    fi
    if (( q > 0 )); then sleep 30; continue; fi   # a real job is waiting for admission: yield
    # load-based (BOT LEAD 10-17): leased-but-idle room is used by filler (nice 19; real jobs keep CPU priority);
    # workers launched in the last 90 s count until the 1-min load average catches up
    load=$(cut -d' ' -f1 /proc/loadavg); now=$(date +%s); pend=0; keep=()
    for x in "${recent[@]}"; do t=${x%:*}; (( now - t < 90 )) && { pend=$(( pend + ${x#*:} )); keep+=("$x"); }; done
    recent=("${keep[@]}")
    lpend=$(python3 -c "print(int(float('$load') + $pend + 0.5))")
    busy=" $(live_groups 2>"$state/backoff.now" | tr '\n' ' ') "
    [[ -s "$state/backoff.now" ]] && log "backoff (died < 90 s with a Traceback, skipped 10 min): $(sort -u "$state/backoff.now" | tr '\n' ' ')"
    # scan ahead from the first unlaunched line: launch the first line whose group has no live block (busy groups
    # are skipped, not waited on), so independent groups stack up to the target
    pick=""; j=$i
    while (( j < i + 400 )); do
        line=$(sed -n "${j}p" "$state/queue" 2>/dev/null); [[ -n "$line" ]] || break
        if ! grep -qx "$j" "$state/launched"; then
            read -r w grp cmd <<< "$line"
            if ! [[ "$w" =~ ^[0-9]+$ ]] || (( w < 1 || w > 12 )) || [[ -z "$cmd" ]]; then
                log "bad line $j: $line"; echo "$j" >> "$state/launched"
            elif [[ "$busy" != *" $grp "* ]]; then pick=$j; break; fi
        fi
        j=$((j+1))
    done
    if [[ -n "$pick" ]] && (( lpend + w <= eff && p + pend + w + 1 <= pcap )); then
        echo "$pick" >> "$state/launched"
        # the filler already applied load + python caps (leased-idle room is not reserved against filler), so the shared
        # check only writes the lease (real jobs see it); CLAIMS/max-live still lowers it on hosts that set one
        BOT_CPU_CAP=1000 "$repo/bot/detach.sh" "$state/blocks/$pick-$grp.log" "$state/blocks/$pick-$grp.receipt.json" \
            "$repo/bot/exit/cpu_job.sh" $((w + 1)) nice -n 19 bash -c "$cmd" > /dev/null
        recent+=("$(date +%s):$w")
        log "launched block $pick group $grp workers $w (load $load + pending $pend, live py $p, target load $eff, python cap $pcap)"
        sleep 20   # let the block start before counting again
        continue
    fi
    sleep 30
done
log "STOP present; filler exits (running blocks continue)"
