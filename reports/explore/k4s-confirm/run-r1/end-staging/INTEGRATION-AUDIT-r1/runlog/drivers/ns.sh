#!/bin/sh
# AUDIT: run a command as if on fake host $1: user+mount+UTS namespace, /mpac/sdicks02 := $FAKEROOT/$1 (bind),
# the real e4v3 venv bound at its usual path inside it (simulated A3 interpreter), hostname $1. Nothing outside changes.
host=$1; shift
exec /usr/bin/unshare -Urmu /bin/sh -c 'mount --bind /mpac/sdicks02/jobs/clasher/e4v3-venv "$1/$2/jobs/clasher/e4v3-venv" && mount --rbind "$1/$2" /mpac/sdicks02 && hostname "$2" && shift 2 && cd / && exec "$@"' ns "$FAKEROOT" "$host" "$@"
