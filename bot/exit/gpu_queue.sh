#!/usr/bin/env bash
# Sequential GPU job queue: keeps one A6000 busy with whatever is appended to QUEUE.
#   bot/exit/gpu_queue.sh QUEUE_FILE
# QUEUE_FILE lines: "<name> <command...>" (blank lines and #comments skipped). Jobs run one at a time in file
# order; a job is done once "<name>" is in QUEUE_FILE.done. Append lines at any time; an empty queue is polled
# every 60 s. Each job logs to <dir of QUEUE_FILE>/<name>.log.
set -uo pipefail
export NUMPY_MADVISE_HUGEPAGE=0  # no THP madvise: direct compaction stalls numpy allocs 2-47 s on fragmented hosts (LIVE LEAD 10-15)
queue=${1:?QUEUE_FILE}; done_file="$queue.done"; dir=$(dirname "$queue")
touch "$done_file"
while true; do
    next=$(grep -v '^\s*#' "$queue" | grep -v '^\s*$' | while read -r name rest; do
        grep -qx "$name" "$done_file" || { echo "$name $rest"; break; }; done)
    if [[ -z "$next" ]]; then sleep 60; continue; fi
    name=${next%% *}; cmd=${next#* }
    echo "$(date -u +%FT%TZ) START $name: $cmd"
    bash -c "$cmd" > "$dir/$name.log" 2>&1
    rc=$?
    echo "$(date -u +%FT%TZ) END $name rc=$rc"
    echo "$name" >> "$done_file"
done
