#!/usr/bin/env bash
# Owned Linux wrapper: detached session, closed stdin, durable PID/PGID receipt.
set -euo pipefail
log=${1:?LOGFILE}; receipt=${2:?RECEIPT}; shift 2
mkdir -p "$(dirname "$log")" "$(dirname "$receipt")"
setsid -f bash -c '
set -euo pipefail
receipt=$1; shift
printf "{\"launched_at_utc\":\"%s\",\"pid\":%s,\"pgid\":%s}\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$$" "$(ps -o pgid= -p $$ | tr -d " ")" > "$receipt"
exec "$@"
' k-detach "$receipt" "$@" > "$log" 2>&1 < /dev/null
for _ in {1..100}; do
    if [[ -s "$receipt" ]]; then cat "$receipt"; exit 0; fi
    sleep .05
done
exit 1
