#!/usr/bin/env bash
set -euo pipefail
cd /mpac/sdicks02/repos/clasher
while [ ! -f /mpac/sdicks02/jobs/clasher/search-ab-primary-127x04-v2.exit ]; do sleep 10; done
test "$(cat /mpac/sdicks02/jobs/clasher/search-ab-primary-127x04-v2.exit)" = 0
bash reports/strategy_council_20260928/fleet/fleet_run.sh search-ab-primary-final300-127x04-v2 taskset -c 0-39 env RAYON_NUM_THREADS=1 .venv/bin/python -m clasher.analysis.loss_review.simulate --out reports/explore/search-ab/primary-final300-127x04 --workers 40 --pairs 300 --pair-offset 700 --seed-base 281474976721356 --delays 27 --arms 0 C R CR --reserve-weight 1 --exclusions reports/explore/search-ab/exclusions.json --resume
