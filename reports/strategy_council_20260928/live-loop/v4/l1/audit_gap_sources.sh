#!/usr/bin/env bash
# Invoke through the leased-host wrapper; no Phase A or model inputs.
set -euo pipefail
label=${1:?fresh job label}
[[ ${CLASHER_LEASE_ROOT:-} == /mpac/sdicks02/repos/clasher-lease ]] || exit 2
root=$CLASHER_LEASE_ROOT
code=$root/repo/reports/strategy_council_20260928/live-loop/v4/l1
destination=$root/data/v4-l2-gap-sources-$label
mkdir "$destination"
rsync -a --checksum --rsync-path='nice -n 10 rsync' \
  --include='*/' --include='public-frames.jsonl.gz' --exclude='*' \
  127x01:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/live-loop/l2/native/ "$destination/"
"$root/envs/clasher-gpu/bin/python" -B "$code/test_gap_schedule_v4.py"
exec "$root/envs/clasher-gpu/bin/python" -B "$code/gap_schedule_v4.py" \
  --l2 "$destination" --output "$root/jobs/$label-source.json"
