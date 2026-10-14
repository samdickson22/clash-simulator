#!/usr/bin/env bash
# Keep a CPU queue (run by bot/exit/gpu_queue.sh, which is device-agnostic) from running dry with label generation:
# whenever QUEUE has no pending job, append the next batch of the latest line whose name starts with PREFIX, with
# --start advanced by --games (disjoint, contiguous index ranges) and --out set to <out base>-s<new start>.
#   bot/exit/cpu_keepalive.sh QUEUE_FILE PREFIX [MAX_BATCHES] [STOP_AT_START]
# STOP_AT_START (optional): never append a batch whose --start would reach this value (keeps a reserved block).
set -uo pipefail
queue=${1:?QUEUE_FILE}; prefix=${2:?PREFIX}; max=${3:-20}; stop_at=${4:-0}; done_file="$queue.done"
touch "$done_file"; n=0
while (( n < max )); do
    pending=$(grep -v '^\s*#' "$queue" | grep -v '^\s*$' | while read -r name rest; do
        grep -qx "$name" "$done_file" || echo "$name"; done | wc -l)
    if (( pending == 0 )); then
        last=$(grep -E "^${prefix}[^ ]* " "$queue" | tail -1)
        start=$(grep -oE -- '--start [0-9]+' <<<"$last" | awk '{print $2}')
        games=$(grep -oE -- '--games [0-9]+' <<<"$last" | awk '{print $2}')
        out=$(grep -oE -- '--out [^ ]+' <<<"$last" | awk '{print $2}')
        if [[ -z "$start" || -z "$games" || -z "$out" ]]; then echo "$(date -u +%FT%TZ) template lacks --start/--games/--out"; sleep 60; continue; fi
        if ! compgen -G "$out/games/*.jsonl" > /dev/null && ! compgen -G "$out/games-*.jsonl" > /dev/null; then
            echo "$(date -u +%FT%TZ) previous batch $out produced no games; stopping (fix the template)"; exit 1; fi
        ns=$((start + games))
        if (( stop_at > 0 && ns + games > stop_at )); then echo "$(date -u +%FT%TZ) reserved block exhausted at $ns"; exit 0; fi
        n=$((n + 1)); name="${prefix}ka$(date -u +%H%M%S)"
        cmd=${last#* }; cmd=${cmd/--start $start/--start $ns}; cmd=${cmd/--out $out/--out ${out%-s*}-s$ns}
        echo "$name $cmd" >> "$queue"
        echo "$(date -u +%FT%TZ) appended $name (start $ns, games $games)"
    fi
    sleep 60
done
echo "$(date -u +%FT%TZ) reached MAX_BATCHES=$max; exiting"
