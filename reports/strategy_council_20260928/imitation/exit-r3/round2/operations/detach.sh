#!/usr/bin/env bash
# Usage: detach.sh LOG [--cwd DIR] COMMAND [ARGS...]
set -euo pipefail
log=${1:?}; shift
cwd=$PWD
if [[ ${1:-} == --cwd ]]; then cwd=$2; shift 2; fi
mkdir -p "$(dirname "$log")"
test ! -e "$log.pid"
setsid -f bash -c '
  cd "$1"; shift
  log=$1; shift
  printf "%s\n" "$$" > "$log.pid"
  printf "{\"pid\":%s,\"pgid\":%s,\"utc\":\"%s\"}\n" "$$" "$(ps -o pgid= -p $$ | tr -d " ")" "$(date -u +%FT%TZ)" > "$log.identity.json"
  exec "$@"
' _ "$cwd" "$log" "$@" < /dev/null > "$log" 2>&1
for i in {1..50}; do
  if [[ -s $log.identity.json ]]; then cat "$log.identity.json"; exit 0; fi
  sleep .1
done
echo 'Detached identity receipt did not arrive' >&2
exit 1
