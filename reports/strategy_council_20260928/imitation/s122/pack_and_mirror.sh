#!/usr/bin/env bash
set -euo pipefail
cd /mpac/sdicks02/repos/clasher
base=reports/strategy_council_20260928/imitation
while [[ ! -f "$base/data/receipts/T9-PASS.json" ]]; do
  if [[ -f /mpac/sdicks02/jobs/clasher/imitation-s122-prepare-20261008-r1.exit ]]; then
    echo 'T9 preparation exited without PASS receipt'; exit 1
  fi
  sleep 10
done
.venv/bin/python "$base/s122/pack_jobs.py"
.venv/bin/python "$base/s122/mirror_t9.py"
