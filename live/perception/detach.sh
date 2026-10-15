#!/bin/bash
# usage: detach.sh LOG CMD...   (runs CMD under setsid+nice, prints PID; for 127x01 live-perception jobs)
log=$1; shift
cd "$(dirname "$(readlink -f "$0")")"   # this checkout's live/perception
# 01 memory is fragmented: numpy THP madvise -> direct-compaction stalls (18 MB alloc took 7-47 s, 2026-10-15)
export NUMPY_MADVISE_HUGEPAGE=0
setsid nohup nice -n 10 "$@" > "$log" 2>&1 < /dev/null &
echo "PID $!"
