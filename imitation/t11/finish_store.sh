#!/usr/bin/env bash
set -euo pipefail
root=/mpac/sdicks02/repos/clasher
cd "$root"
exit_file=/mpac/sdicks02/jobs/clasher/t11-store-build-20261008-r1.exit
while [[ ! -f "$exit_file" ]]; do sleep 30; done
[[ $(cat "$exit_file") == 0 ]]
export PYTHONPATH="$root"
.venv/bin/python -B -m imitation.t11.baseline \
  --store reports/strategy_council_20260928/imitation/data/v2-store-v1 \
  --out reports/strategy_council_20260928/imitation/data/t11-baselines-v1 --workers 8
rsync -c reports/strategy_council_20260928/imitation/data/receipts/T11-STORE-PASS.json \
  127x05:"$root"/reports/strategy_council_20260928/imitation/data/receipts/
rsync -c reports/strategy_council_20260928/imitation/data/t11-baselines-v1/frequency-dev.json \
  reports/strategy_council_20260928/imitation/data/t11-baselines-v1/frequency-fit.json \
  127x05:"$root"/imitation/t11/receipts/
