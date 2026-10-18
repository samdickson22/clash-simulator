#!/usr/bin/env bash
# Hourly off-host copy of an RL run's durable state (snapshots, learner state, train log, evals) to a second host.
#   bot/rl/mirror.sh RUN DST_HOST DST_DIR [EVERY=3600]
# Pushes RUN/{policies,snapshots,evals}/, learner-state.pt, learner.json, train.jsonl and actor-*.json with rsync -a
# (no --delete: the mirror keeps everything). policies/ holds LATEST (absolute paths), so restore by rsyncing the
# mirror back to the same RUN path before a --resume. Stops when RUN/STOP_MIRROR exists. Never touches the source run.
set -uo pipefail
run=${1:?RUN}; host=${2:?DST_HOST}; dst=${3:?DST_DIR}; every=${4:-3600}
ssh "$host" "mkdir -p '$dst'" || exit 1
while [[ ! -e "$run/STOP_MIRROR" ]]; do
    shopt -s nullglob
    files=("$run"/learner-state.pt "$run"/learner.json "$run"/train.jsonl "$run"/actor-*.json)
    dirs=(); for d in policies snapshots evals; do [[ -d "$run/$d" ]] && dirs+=("$run/$d"); done
    shopt -u nullglob
    # LATEST is read BEFORE policies/ is listed, so the copied pointer always names a file the copy contains (the
    # learner writes the policy file before LATEST, and never deletes the newest one); it lands last
    latest=$(mktemp); cp "$run/policies/LATEST" "$latest" 2>/dev/null
    if rsync -a --exclude LATEST "${files[@]}" "${dirs[@]}" "$host:$dst/" \
        && { [[ ! -s "$latest" ]] || { ssh "$host" "mkdir -p '$dst/policies'" && rsync -a "$latest" "$host:$dst/policies/LATEST"; }; }; then
        echo "$(date -u +%FT%TZ) mirrored $(du -sh "$run/snapshots" 2>/dev/null | cut -f1) snapshots to $host:$dst"
    else
        echo "$(date -u +%FT%TZ) mirror FAILED"
    fi
    rm -f "$latest"
    for _ in $(seq "$((every / 30))"); do [[ -e "$run/STOP_MIRROR" ]] && break; sleep 30; done
done
