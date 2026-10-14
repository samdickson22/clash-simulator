#!/usr/bin/env bash
# Overlapping CPU feeder for ExIt label generation: start the next batch before the current one's tail ends.
#   bot/exit/cpu_feeder.sh STATE_DIR TEMPLATE_FILE TARGET_WORKERS BATCH_GAMES NEXT_START STOP_AT [CAP] [MAX_BATCHES]
# TEMPLATE_FILE holds one generate command containing the literal tokens __OUT__, __START__, __GAMES__, __WORKERS__.
# Every 30 s: if live (non-zombie) generate processes < TARGET and the host has room under CAP live python processes,
# launch a batch on [NEXT_START, NEXT_START+BATCH) with workers = min(TARGET - live gen, CAP - live - 4 - leases) (min 8), detached, out
# STATE_DIR/../gen-ka-s<start>. NEXT_START is persisted in STATE_DIR/next_start (restarts never reuse a range).
# Stops when NEXT_START+BATCH > STOP_AT, after MAX_BATCHES, or if a finished batch produced no games.
set -uo pipefail
state=${1:?}; tmpl=${2:?}; target=${3:?}; batch=${4:?}; first=${5:?}; stop_at=${6:?}; cap=${7:-105}; max=${8:-200}
repo=/mpac/sdicks02/repos/clasher-bot
mkdir -p "$state"; [[ -s "$state/next_start" ]] || echo "$first" > "$state/next_start"
jobs_dir=$(dirname "$state"); n=0
live_py() { ps -u "$USER" -o stat=,args= | grep -v '^Z' | grep -c '[p]ython'; }
claimed() {  # processes reserved by bot/exit/cpu_room.sh waiters (full N) and by running leases (N minus the
    # lease's live python processes, so gaps between a job's phases are not handed to new batches); dead pids ignored
    local t=0 f n g used
    for f in /mpac/sdicks02/jobs/clasher/bot-cpu-claims/claim-*; do
        [[ -e "$f" ]] && kill -0 "${f##*claim-}" 2>/dev/null && t=$(( t + $(cat "$f") ))
    done
    local seen=" "
    for f in /mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-*; do
        [[ -e "$f" ]] && kill -0 "${f##*lease-}" 2>/dev/null || continue
        read -r n g < "$f"
        [[ "$seen" == *" $g "* ]] && continue   # several lease files for one process group count once
        seen="$seen$g "
        used=$(ps -u "$USER" -o pgid=,stat=,args= | awk -v g="$g" '$1 == g && $2 !~ /^Z/ && /[p]ython/' | wc -l)
        (( n > used )) && t=$(( t + n - used ))
    done; echo "$t"; }
live_gen() { ps -u "$USER" -o stat=,args= | grep -v '^Z' | grep -c '[b]ot\.exit\.generate'; }
while (( n < max )); do
    # guard: every batch whose launcher has exited must have produced games
    for r in "$state"/batch-*.receipt.json; do
        [[ -e "$r" ]] || continue
        s=$(basename "$r" .receipt.json); s=${s#batch-}; pid=$(python3 -c "import json;print(json.load(open('$r'))['pid'])")
        if ! kill -0 "$pid" 2>/dev/null && [[ ! -e "$state/checked-$s" ]]; then
            if compgen -G "$jobs_dir/gen-ka-s$s/games-*.jsonl" > /dev/null || compgen -G "$jobs_dir/gen-ka-s$s/games/*.jsonl" > /dev/null; then
                touch "$state/checked-$s"
            else echo "$(date -u +%FT%TZ) batch $s produced no games; stopping"; exit 1; fi
        fi
    done
    g=$(live_gen); p=$(live_py)
    if (( g < target )); then
        room=$(( cap - p - 4 - $(claimed) )); want=$(( target - g )); w=$(( room < want ? room : want ))
        start=$(cat "$state/next_start")
        if (( start + batch > stop_at )); then echo "$(date -u +%FT%TZ) block exhausted at $start"; exit 0; fi
        if (( w >= 8 )); then
            echo $(( start + batch )) > "$state/next_start"
            cmd=$(sed "s#__OUT__#$jobs_dir/gen-ka-s$start#g; s#__START__#$start#g; s#__GAMES__#$batch#g; s#__WORKERS__#$w#g" "$tmpl")
            "$repo/bot/detach.sh" "$state/batch-$start.log" "$state/batch-$start.receipt.json" bash -c "$cmd" > /dev/null
            n=$((n + 1)); echo "$(date -u +%FT%TZ) launched batch $start (+$batch games, $w workers; live gen $g, live py $p)"
        fi
    fi
    sleep 30
done
echo "$(date -u +%FT%TZ) reached MAX_BATCHES=$max"
