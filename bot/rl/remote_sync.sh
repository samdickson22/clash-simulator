#!/usr/bin/env bash
# Run bot.rl actors on a second host: mirror the learner's policies/snapshots here, push finished rollouts there.
#   bot/rl/remote_sync.sh LEARNER_HOST RUN [EVERY=15]
# RUN is the same absolute path on both hosts (LATEST/LIST hold absolute paths). Policy and snapshot files are
# pulled AFTER their LATEST/LIST pointers are read (pointers land last), so a pointer never names a missing file: the
# learner writes a file before its pointer, so files listed after the pointer read include everything it names.
# Rollouts move with
# --remove-source-files (the actor's back-pressure counts local files). STOP_ACTORS on the learner host propagates.
set -uo pipefail
src=${1:?}; run=${2:?}; every=${3:-15}
mkdir -p "$run/policies" "$run/snapshots" "$run/rollouts"
all_present() { local p; while read -r p; do [[ -s "$p" ]] || return 1; done < "$1"; }
while [[ ! -e "$run/STOP_SYNC" ]]; do
    # the pointer is promoted only if the file it names arrived (the learner may prune it between the two pulls)
    rsync -a "$src:$run/policies/LATEST" "$run/policies/.LATEST.next" \
        && rsync -a --exclude LATEST --exclude '.LATEST.next' --exclude '*.partial' "$src:$run/policies/" "$run/policies/" \
        && read -r _ p < "$run/policies/.LATEST.next" && [[ -s "$p" ]] \
        && mv "$run/policies/.LATEST.next" "$run/policies/LATEST"
    if rsync -a "$src:$run/snapshots/LIST" "$run/snapshots/.LIST.next" 2>/dev/null; then
        rsync -a --exclude LIST --exclude '.LIST.next' --exclude '*.partial' "$src:$run/snapshots/" "$run/snapshots/" \
            && all_present "$run/snapshots/.LIST.next" \
            && mv "$run/snapshots/.LIST.next" "$run/snapshots/LIST"
    else
        rsync -a --exclude LIST --exclude '*.partial' "$src:$run/snapshots/" "$run/snapshots/"
    fi
    shopt -s nullglob; files=("$run"/rollouts/v*.npz); shopt -u nullglob
    (( ${#files[@]} )) && rsync -a --remove-source-files "${files[@]}" "$src:$run/rollouts/"
    rsync -a "$run"/rollouts/games-*.jsonl "$src:$run/rollouts/" 2>/dev/null
    ssh "$src" "test -e '$run/STOP_ACTORS'" && touch "$run/STOP_ACTORS"
    sleep "$every"
done
