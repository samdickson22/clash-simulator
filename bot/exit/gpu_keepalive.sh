#!/usr/bin/env bash
# Keep a gpu_queue.sh queue from running dry: whenever QUEUE has no pending job, append a replicate of the most
# recent line whose name starts with PREFIX, with --seed incremented and a fresh --out directory.
#   bot/exit/gpu_keepalive.sh QUEUE_FILE PREFIX [MAX_FILLERS]
# Real work can still be appended to QUEUE at any time; fillers only appear when nothing else is pending.
set -uo pipefail
queue=${1:?QUEUE_FILE}; prefix=${2:?PREFIX}; max=${3:-6}; done_file="$queue.done"
touch "$done_file"; n=0
while (( n < max )); do
    pending=$(grep -v '^\s*#' "$queue" | grep -v '^\s*$' | while read -r name rest; do
        grep -qx "$name" "$done_file" || echo "$name"; done | wc -l)
    if (( pending == 0 )); then
        last=$(grep -E "^${prefix}[^ ]* " "$queue" | tail -1)
        if [[ -z "$last" ]]; then echo "$(date -u +%FT%TZ) no ${prefix}* template in $queue"; sleep 60; continue; fi
        seed=$(grep -oE -- '--seed [0-9]+' <<<"$last" | awk '{print $2}')
        out=$(grep -oE -- '--out [^ ]+' <<<"$last" | awk '{print $2}')
        [[ -z "$seed" || -z "$out" ]] && { echo "template lacks --seed/--out"; sleep 60; continue; }
        ns=$((seed + 1)); n=$((n + 1)); name="${prefix}ka$(date -u +%H%M%S)"
        cmd=${last#* }; cmd=${cmd/--seed $seed/--seed $ns}; cmd=${cmd/--out $out/--out ${out%-ka*}-ka$ns}
        echo "$name $cmd" >> "$queue"
        echo "$(date -u +%FT%TZ) appended $name (seed $ns)"
    fi
    sleep 60
done
echo "$(date -u +%FT%TZ) reached MAX_FILLERS=$max; exiting"
