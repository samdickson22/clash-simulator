#!/usr/bin/env bash
set -euo pipefail
root=/mpac/sdicks02/repos/clasher
cd "$root"
base=reports/strategy_council_20260928/imitation
while [[ ! -f "$base/data/receipts/T9-C56-equality.json" ]]; do
  if [[ -f /mpac/sdicks02/jobs/clasher/imitation-s122-c56-refilter-20261008-r1.exit ]]; then
    echo 'C56 refilter exited without equality receipt'; exit 1
  fi
  sleep 10
done
.venv/bin/python "$base/s122/build_payloads.py"
.venv/bin/python "$base/s122/build_roles.py"
