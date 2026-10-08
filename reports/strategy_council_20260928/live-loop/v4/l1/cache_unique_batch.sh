#!/usr/bin/env bash
# Continue new unique shards on 16; preserve completed replicas on 01/18.
set -euo pipefail
label=${1:?fresh label}; base_manifest=${2:?verified base manifest}; base_inventory=${3:?pinned base inventory}
[[ $(hostname -s) == 127x16 && ${CLASHER_LEASE_ROOT:-} == /mpac/sdicks02/repos/clasher-lease ]] || exit 2
users=$("$HOME/.local/bin/fleet-console-users")
[[ $users == 0 ]] || { echo '24-worker extension requires no console users'; exit 75; }
code=$CLASHER_ROOT/reports/strategy_council_20260928/live-loop/v4/l1
python=$CLASHER_LEASE_ROOT/envs/clasher-gpu/bin/python
source=$CLASHER_LEASE_ROOT/data/v4-matches
cache=$CLASHER_LEASE_ROOT/data/v4-cache
jobs=$CLASHER_LEASE_ROOT/jobs
split=$CLASHER_ROOT/reports/strategy_council_20260928/live-loop/v4/split.json
"$python" -B "$code/stage_training.py" --destination "$source" --split "$split"
cp -p "$source/stage-inventory.json" "$jobs/$label-stage.json"
"$python" -B "$code/cache_extension_v4.py" --current "$jobs/$label-stage.json" \
  --base-manifest "$base_manifest" --base-inventory "$base_inventory" --output "$jobs/$label-plan.json"
"$python" -B "$code/build_cache.py" --source "$source" --cache "$cache" --split "$split" \
  --inventory "$jobs/$label-plan.json" --workers 24 --budget-gb 214 --receipt "$jobs/$label-build.json"
exec "$python" -B "$code/cache_manifest.py" --source "$source" --cache "$cache" --split "$split" \
  --inventory "$jobs/$label-plan.json" --output "$jobs/$label-manifest.json"
