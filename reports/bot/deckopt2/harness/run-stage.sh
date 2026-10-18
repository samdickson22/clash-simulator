#!/usr/bin/env bash
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -euo pipefail
root=/mpac/sdicks02/jobs/clasher/bot-deckopt2
source "$root/env.sh"
stage=${1:?stage}; shard=${2:?shard}
case "$(hostname -s)" in 127x01|127x03) ;; *) exit 2 ;; esac
while [[ ! -f "$root/$stage/bank.json" ]]; do sleep 5; done
date -u
set +e
bot/exit/cpu_job.sh 9 nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -m bot.deckopt2.run run --root "$root" --stage "$stage" --shard "$shard" --shards 4 --workers 8
status=$?
printf '%s\n' "$status" > "$root/$stage-exit-$shard.txt"
date -u
exit "$status"
