#!/usr/bin/env bash
# Run only through fleet_run.sh or the live lease run.sh. No background children.
set -euo pipefail
action=${1:?migrate or build}; label=${2:?unique receipt label}
host=$(hostname -s)
case $host in
  127x01)
    root=/mpac/sdicks02/repos/clasher
    python=/mpac/sdicks02/envs/clasher-gpu/bin/python
    cache=/mpac/sdicks02/repos/clasher-v4-cache
    source=/mpac/sdicks02/repos/clasher-v4-data/matches
    legacy=/mpac/sdicks02/repos/clasher-v4-data/cache
    jobs=/mpac/sdicks02/jobs/clasher ;;
  127x16|127x18)
    [[ ${CLASHER_LEASE_ROOT:-} == /mpac/sdicks02/repos/clasher-lease ]] || exit 2
    root=$CLASHER_LEASE_ROOT/repo
    python=$CLASHER_LEASE_ROOT/envs/clasher-gpu/bin/python
    cache=$CLASHER_LEASE_ROOT/data/v4-cache
    source=$CLASHER_LEASE_ROOT/data/v4-matches
    legacy=$CLASHER_LEASE_ROOT/cache/v4-pixels-r2
    jobs=$CLASHER_LEASE_ROOT/jobs ;;
  *) echo 'Cache batch host not configured' >&2; exit 2 ;;
esac
code=$root/reports/strategy_council_20260928/live-loop/v4/l1
split=$root/reports/strategy_council_20260928/live-loop/v4/split.json
users=$("$HOME/.local/bin/fleet-console-users")
[[ $users =~ ^[0-9]+$ ]] || { echo 'Invalid console helper response' >&2; exit 2; }
if [[ $action == build ]]; then
  partition=${3:?partition}; partitions=${4:?partitions}; workers=${5:?workers}; budget=${6:-280}
  (( users == 0 || workers + 4 <= 16 )) || { echo 'Console cap' >&2; exit 75; }
fi
"$python" -B - "$legacy" "$cache" "$jobs/$label-migration.json" "$code" <<'PY'
import datetime,json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[4])
from cache_budget import approved_root,require_growth
old,new,receipt=map(Path,sys.argv[1:4]);moves=[]
if new != approved_root():raise ValueError('Unapproved destination')
if old.exists():
    if new.exists():raise ValueError('Both migration roots exist; inspect before changing')
    old.rename(new);moves.append([str(old),str(new)])
new.mkdir(parents=True,exist_ok=True)
failed=old.parent/'v4-pixels'
if old.name=='v4-pixels-r2' and failed.exists():
    target=new/'retained-legacy-failed'
    if target.exists():raise ValueError('Retained legacy destination already exists')
    failed.rename(target);moves.append([str(failed),str(target)])
require_growth(new,0)
with receipt.open('x') as f:
    json.dump(dict(moves=moves,cache=str(new),no_data_deleted=True,
                   utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),f,indent=2)
PY
[[ $action != migrate ]] || exit 0
[[ $action == build ]] || exit 2
if [[ $host != 127x01 ]]; then
  # T7 host 18 needs the full training population locally; 16 is a decode shard.
  stage_args=()
  if [[ $host == 127x16 ]]; then stage_args=(--partition "$partition" --partitions "$partitions"); fi
  "$python" -B "$code/stage_training.py" --destination "$source" --split "$split" "${stage_args[@]}"
  cp -p "$source/stage-inventory.json" "$jobs/$label-stage.json"
  # Reuse all five existing pilot caches, including 0700 missing on 16.
  "$python" -B "$code/sync_pixel_cache.py" --from-host 127x01 \
    --remote-cache /mpac/sdicks02/repos/clasher-v4-cache --cache "$cache" \
    --source "$source" --split "$split" --receipt "$jobs/$label-pilot-copy.json" \
    --episodes v4-phase-a-1975100700 v4-phase-a-1975100701 v4-phase-a-1975100702 v4-phase-a-1975100703 v4-phase-a-1975100708
fi
exec "$python" -B "$code/build_cache.py" --source "$source" --split "$split" \
  --cache "$cache" --workers "$workers" --partition "$partition" --partitions "$partitions" \
  --budget-gb "$budget" --receipt "$jobs/$label-build.json"
