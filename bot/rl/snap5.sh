#!/usr/bin/env bash
# Extra snapshots: every version divisible by N (the learner itself snapshots every --snapshot-every) is copied to
# RUN/snapshots/, appended to the league LIST and queued in RUN/evalq/.
#   bot/rl/snap5.sh RUN [N=5]
set -uo pipefail
run=${1:?}; n=${2:-5}
while [[ ! -e "$run/STOP_LEARNER" ]]; do
    read -r v path < "$run/policies/LATEST"
    name=$(basename "$path" .pt)
    if (( v > 0 && v % n == 0 )) && [[ ! -e "$run/snapshots/$name.pt" ]] && [[ -s "$path" ]]; then
        cp "$path.calibration.json" "$run/snapshots/$name.pt.calibration.json"
        cp "$path" "$run/snapshots/.$name.pt.partial" && mv "$run/snapshots/.$name.pt.partial" "$run/snapshots/$name.pt"
        echo "$run/snapshots/$name.pt" >> "$run/snapshots/LIST"
        echo "$run/snapshots/$name.pt" > "$run/evalq/$name"
        echo "$(date -u +%FT%TZ) snapshot $name"
    fi
    sleep 20
done
