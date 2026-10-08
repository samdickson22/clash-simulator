#!/usr/bin/env bash
set -euo pipefail
cd /mpac/sdicks02/repos/clasher
base=reports/strategy_council_20260928/imitation
job=/mpac/sdicks02/jobs/clasher/imitation-s122-qa-20261008-r2.exit
while [[ ! -f "$job" ]]; do sleep 10; done
[[ $(cat "$job") == 0 ]] || { echo 'QA extraction failed; production remains blocked'; exit 1; }
.venv/bin/python "$base/s122/extract_s122.py" repeat --workers 2
.venv/bin/python "$base/s122/extract_s122.py" baseline --workers 2
.venv/bin/python "$base/s122/qa_s122.py"
rsync -c -R "$base/data/receipts/T10-QA-PASS.json" 127x03:/mpac/sdicks02/repos/clasher/
