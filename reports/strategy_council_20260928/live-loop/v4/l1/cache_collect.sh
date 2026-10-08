#!/usr/bin/env bash
# Gather complete immutable shards; invoke through fleet/lease wrapper.
set -euo pipefail
label=${1:?fresh receipt label}; inventory=${2:?explicit staged snapshot JSON}
host=$(hostname -s)
case $host in
  127x01)
    root=/mpac/sdicks02/repos/clasher
    python=/mpac/sdicks02/envs/clasher-gpu/bin/python
    cache=/mpac/sdicks02/repos/clasher-v4-cache
    source=/mpac/sdicks02/repos/clasher-v4-data/matches
    jobs=/mpac/sdicks02/jobs/clasher
    senders=(127x16 127x18)
    workers=$(ps -u "$(id -un)" -o comm= | awk '$1 ~ /^python/ {n++} END {print n+0}')
    cap=96
    users=$("$HOME/.local/bin/fleet-console-users")
    [[ $users =~ ^[0-9]+$ ]] || exit 2
    (( users == 0 )) || cap=16
    (( workers + 6 <= cap )) || { echo 'Insufficient hub process headroom'; exit 75; } ;;
  127x18)
    [[ ${CLASHER_LEASE_ROOT:-} == /mpac/sdicks02/repos/clasher-lease ]] || exit 2
    root=$CLASHER_LEASE_ROOT/repo
    python=$CLASHER_LEASE_ROOT/envs/clasher-gpu/bin/python
    cache=$CLASHER_LEASE_ROOT/data/v4-cache
    source=$CLASHER_LEASE_ROOT/data/v4-matches
    jobs=$CLASHER_LEASE_ROOT/jobs
    senders=(127x16) ;;
  *) echo 'Gather host not configured' >&2; exit 2 ;;
esac
code=$root/reports/strategy_council_20260928/live-loop/v4/l1
split=$root/reports/strategy_council_20260928/live-loop/v4/split.json
for sender in "${senders[@]}"; do
  "$python" -B "$code/sync_pixel_cache.py" --from-host "$sender" \
    --remote-cache /mpac/sdicks02/repos/clasher-lease/data/v4-cache \
    --cache "$cache" --source "$source" --split "$split" --receipt "$jobs/$label-$sender-copy.json"
done
exec "$python" -B "$code/cache_manifest.py" --source "$source" --cache "$cache" \
  --split "$split" --inventory "$inventory" --output "$jobs/$label-manifest.json"
