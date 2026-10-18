#!/usr/bin/env bash
# Owned Linux wrapper: detached session, closed stdin, durable PID/PGID receipt.
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -euo pipefail
export NUMPY_MADVISE_HUGEPAGE=0  # no THP madvise: direct compaction stalls numpy allocs 2-47 s on fragmented hosts (LIVE LEAD 10-15)
log=${1:?LOGFILE}; receipt=${2:?RECEIPT}; shift 2
mkdir -p "$(dirname "$log")" "$(dirname "$receipt")"
setsid -f bash -c '
set -euo pipefail
receipt=$1; shift
printf "{\"launched_at_utc\":\"%s\",\"pid\":%s,\"pgid\":%s}\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$$" "$(ps -o pgid= -p $$ | tr -d " ")" > "$receipt"
exec "$@"
' bot-detach "$receipt" "$@" > "$log" 2>&1 < /dev/null
for _ in {1..100}; do
    if [[ -s "$receipt" ]]; then cat "$receipt"; exit 0; fi
    sleep .05
done
exit 1
