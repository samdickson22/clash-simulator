#!/usr/bin/env bash
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/bot-deckopt2
source "$job/env.sh"
export PYTHONPATH=/mpac/sdicks02/repos/clasher-bot-deckopt2
root=${1:?ROOT}; stage=${2:?STAGE}; shard=${3:?SHARD}; workers=${4:?WORKERS}; shards=${5:-4}
case "$(hostname -s)" in 127x01|127x03|127x04) ;; *) exit 2 ;; esac
[[ "$root" == "$job/"* ]] || exit 2
[[ "$workers" =~ ^[0-9]+$ ]] && (( workers >= 1 && workers <= 40 )) || exit 2
date -u
set +e
/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh "$((workers+1))" nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python "$job/execute.py" --root "$root" --stage "$stage" --shard "$shard" --shards "$shards" --workers "$workers"
status=$?
printf '%s\n' "$status" > "$root/$stage-exit-$shard.txt"
date -u
exit "$status"
