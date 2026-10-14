#!/bin/sh
# r4 CHAIN (copy of the audit's ns.sh): run a command as if on fake host $1: user+mount+UTS namespace,
# /mpac/sdicks02 := /tmp/k4s-r4chainc-ieyb5y/hosts/$1 (rbind), 05's e4v3-venv bound read-only at its usual path (SIMULATED A3), hostname $1.
host=$1; shift
exec /usr/bin/unshare -Urmu /bin/sh -c 'mount --bind -o ro /mpac/sdicks02/jobs/clasher/e4v3-venv "$1/$2/jobs/clasher/e4v3-venv" && mount --rbind "$1/$2" /mpac/sdicks02 && hostname "$2" && shift 2 && cd / && exec "$@"' ns "/tmp/k4s-r4chainc-ieyb5y/hosts" "$host" "$@"
