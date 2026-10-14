#!/usr/bin/env bash
# Off-host copy of a bot-exit job dir (checkpoints, packed corpora, receipts), every 30 min.
#   bot/exit/mirror.sh /mpac/sdicks02/jobs/clasher/bot-exit-r1 127x04
# Destination is a dedicated mirror prefix (<job>-mirror on the target host), never a live path.
# Raw per-game shards (gen-*/games) are skipped: the packed corpora hold the same rows.
set -euo pipefail
src=${1:?JOB_DIR}; host=${2:-127x04}; every=${3:-1800}
dst="$(dirname "$src")/$(basename "$src")-mirror/"
while true; do
    ssh "$host" "mkdir -p '$dst'"
    nice -n 19 rsync -a --exclude 'gen-*/games/' --exclude 'selftest/' --exclude '*.partial' "$src/" "$host:$dst" \
        && echo "$(date -u +%FT%TZ) mirrored $src -> $host:$dst" || echo "$(date -u +%FT%TZ) mirror FAILED"
    sleep "$every"
done
