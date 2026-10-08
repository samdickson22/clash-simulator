#!/bin/bash
# Delete bulky, untracked Clasher data from the Mac ONLY after two fleet copies match it by checksum.
# Keeps: git-tracked files, .venv, live-loop/, the emulator cache (~/.cache/clasher-native-reference),
# and the small data the live-loop code reads (m0/data, search-tuning, pilot/v7r4h-launch, pilot/*.json).
# Usage: offload_mac_bulk.sh [--delete]   (default is a verify-only dry run)
set -euo pipefail
SRC=/Users/sam/Desktop/code/clasher
NODES=(127x01 127x04)
DST=/mpac/sdicks02/repos/clasher
RS=/opt/homebrew/bin/rsync
LOGD=$SRC/reports/strategy_council_20260928/pilot/logs
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LIST=$LOGD/offload-mac-bulk-$STAMP.files
cd "$SRC"
DIRS=(
  reports/strategy_council_20260928/m0/readiness
  checkpoints
  datasets
  reports/strategy_council_20260928/c56/data
  reports/strategy_council_20260928/human-prior-p16
  reports/persistent_batch_v1
  reports/strategy_council_20260928/pilot/v7r1-launch
  reports/strategy_council_20260928/pilot/v7r2-launch
  reports/strategy_council_20260928/pilot/v7r2c-launch
)
# untracked files only (including ignored); tracked files stay and remain restorable from git
git ls-files -o -z -- "${DIRS[@]}" | tr '\0' '\n' | grep -v -E '(^|/)(\.DS_Store|__pycache__/)' > "$LIST"
n=$(wc -l < "$LIST"); bytes=$(tr '\n' '\0' < "$LIST" | xargs -0 stat -f%z | awk '{s+=$1} END {print s}')
echo "$STAMP candidates: $n files, $bytes bytes"
for h in "${NODES[@]}"; do
  d=$($RS -an --checksum --itemize-changes --files-from="$LIST" -e "ssh -o ControlMaster=no" ./ "$h:$DST/" | grep -c -E '^[<c>]' || true)
  echo "$h checksum differences: $d"
  [ "$d" -eq 0 ] || { echo "ABORT: $h copy incomplete or different"; exit 1; }
done
echo "verified on ${NODES[*]}"
[ "${1:-}" = --delete ] || { echo "dry run only (pass --delete)"; exit 0; }
tr '\n' '\0' < "$LIST" | xargs -0 rm -f
for d in "${DIRS[@]}"; do [ -d "$d" ] && find "$d" -type d -empty -delete; done
echo "$STAMP deleted $n files ($bytes bytes); list: $LIST; copies: ${NODES[*]}:$DST"
