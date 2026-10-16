#!/usr/bin/env bash
# On 05: export origin/main (committed files only) into a run tree and push it plus the model dirs to hosts.
#   bot/fullpool/run/stage.sh [REV=origin/main] HOST...      -> prints the tree path J/repo-<sha12>
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../../.." && pwd); J=${J:-/mpac/sdicks02/jobs/clasher/bot-fullpool}
REV=origin/main; [[ "${1:-}" == */* || "${1:-}" =~ ^[0-9a-f]{7,40}$ ]] && { REV=$1; shift; }
git -C "$REPO" fetch -q origin
SHA=$(git -C "$REPO" rev-parse --short=12 "$REV"); T=$J/repo-$SHA
mkdir -p "$T"
git -C "$REPO" archive "$SHA" bot reports/explore/x4s reports/bot/fullpool/freq reports/live/loop/arena-card-freq.json \
  reports/live/loop/ARENA-CARDS.md | tar -x -C "$T"
echo "$SHA" > "$T/STAGED-REV"
for h in "$@"; do
  ssh "127x$h" "mkdir -p $T $J/ext $J/lopp-fp $J/meta"
  rsync -a "$T/" "127x$h:$T/"
  rsync -a "$J/ext/" "127x$h:$J/ext/"; rsync -a "$J/lopp-fp/" "127x$h:$J/lopp-fp/"; rsync -a "$J/meta/" "127x$h:$J/meta/"
  echo "127x$h: $T"
done
echo "$T"
