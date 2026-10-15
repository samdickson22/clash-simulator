#!/usr/bin/env bash
# Run bot.rl actors on a second host: mirror the learner's policies/snapshots here, push finished rollouts there.
#   bot/rl/remote_sync.sh LEARNER_HOST RUN [EVERY=15]
# RUN is the same absolute path on both hosts (LATEST/LIST hold absolute paths). Policy and snapshot files are
# pulled before the LATEST/LIST pointers, so a pointer never names a missing file. Rollouts move with
# --remove-source-files (the actor's back-pressure counts local files). STOP_ACTORS on the learner host propagates.
set -uo pipefail
src=${1:?}; run=${2:?}; every=${3:-15}
mkdir -p "$run/policies" "$run/snapshots" "$run/rollouts"
while [[ ! -e "$run/STOP_SYNC" ]]; do
    rsync -a --exclude LATEST "$src:$run/policies/" "$run/policies/" && rsync -a "$src:$run/policies/LATEST" "$run/policies/"
    rsync -a --exclude LIST "$src:$run/snapshots/" "$run/snapshots/" && { rsync -a "$src:$run/snapshots/LIST" "$run/snapshots/" 2>/dev/null || true; }
    shopt -s nullglob; files=("$run"/rollouts/v*.npz); shopt -u nullglob
    (( ${#files[@]} )) && rsync -a --remove-source-files "${files[@]}" "$src:$run/rollouts/"
    rsync -a "$run"/rollouts/games-*.jsonl "$src:$run/rollouts/" 2>/dev/null
    ssh "$src" "test -e '$run/STOP_ACTORS'" && touch "$run/STOP_ACTORS"
    sleep "$every"
done
