#!/usr/bin/env bash
set -euo pipefail
source /mpac/sdicks02/repos/clasher-lease/env.sh
label=${1:?unique-label}; shift
[[ $label =~ ^[a-zA-Z0-9._-]+$ ]] || exit 2
mkdir -p "$CLASHER_LEASE_ROOT/jobs"
[[ ! -e $CLASHER_LEASE_ROOT/jobs/$label.exit.json && ! -e $CLASHER_LEASE_ROOT/jobs/$label.launch.pid ]] || { echo 'Use a fresh label'; exit 2; }
nohup setsid nice -n 10 /usr/bin/python3 "$CLASHER_LEASE_ROOT/lease_watch.py" "$label" "$@" >"$CLASHER_LEASE_ROOT/jobs/$label.log" 2>&1 < /dev/null &
printf '%s\n' "$!" >"$CLASHER_LEASE_ROOT/jobs/$label.launch.pid"
printf 'pid=%s log=%s/jobs/%s.log\n' "$!" "$CLASHER_LEASE_ROOT" "$label"
