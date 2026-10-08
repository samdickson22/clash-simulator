#!/usr/bin/env bash
set -euo pipefail
run=${1:?T6 run}; dataset=${2:?dataset}; output=${3:?gap output}
for ((attempt=0; attempt<240; attempt++)); do
  if [[ -f $run/complete.json ]]; then
    exec /mpac/sdicks02/envs/clasher-gpu/bin/python reports/strategy_council_20260928/live-loop/v4/l1/gap_t6.py \
      --dataset "$dataset" --run "$run" --l2 reports/strategy_council_20260928/live-loop/l2/native --output "$output"
  fi
  sleep 15
done
echo 'T6 validation did not finish within one hour; no gap job started' >&2
exit 75
