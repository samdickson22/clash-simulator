#!/usr/bin/env bash
set -euo pipefail
cd /mpac/sdicks02/repos/clasher
mkdir -p reports/explore/search-ab/receipts/home reports/explore/search-ab/receipts/leased
for label in search-ab-baseline-reproduction-v1 search-ab-baseline-reproduction-v2 search-ab-tests-v3 search-ab-tests-v4 search-ab-native-check-v1 search-ab-native-check-v2 search-ab-budget100-04-v1 search-ab-leased-scheduler-v1 search-ab-leased-scheduler-v2 search-ab-leased-scheduler-v3 search-ab-leased-scheduler-v4 search-ab-leased-scheduler-v5 search-ab-leased-scheduler-v6 search-ab-leased-scheduler-v7 search-ab-leased-scheduler-v8 search-ab-leased-scheduler-v9 search-ab-leased-scheduler-v10 search-ab-leased-scheduler-v11 search-ab-leased-scheduler-v12 search-ab-leased-scheduler-v13 search-ab-leased-scheduler-v14 search-ab-belief-profile-v1 search-ab-belief-profile-v2 search-ab-belief-profile-v3 search-ab-alias-check-v1 search-ab-budget100-full-04-v1 search-ab-tests-v5 search-ab-tests-v6 search-ab-leased-scheduler-v15 search-ab-leased-scheduler-v16 search-ab-pause-parity-v2 search-ab-finalize-v1 search-ab-pause-parity-v3 search-ab-estimate-costs-v1 search-ab-tests-v7 search-ab-tests-v8 search-ab-tests-v9 search-ab-tests-v10 search-ab-startup-check-v2 search-ab-balancing-check-v1 search-ab-collect-receipts-v2 search-ab-finalize-v2 search-ab-qualify-v1 search-ab-qualify-v2 search-ab-finalize-v3; do
 for suffix in log exit pid; do
  src=/mpac/sdicks02/jobs/clasher/$label.$suffix
  if [ -f "$src" ]; then cp "$src" reports/explore/search-ab/receipts/home/; fi
 done
done
for src in /mpac/sdicks02/jobs/clasher/cpu-search-ab-*; do
 [ -f "$src" ] && cp "$src" reports/explore/search-ab/receipts/home/
done
for host in 127x09 127x13 127x14 127x15 127x16; do
 mkdir -p "reports/explore/search-ab/receipts/leased/$host"
 rsync -ac --include='cpu-search-ab-*.log' --include='cpu-search-ab-*.state.json' --include='cpu-search-ab-*.exit.json' --include='cpu-search-ab-*.launch.pid' --exclude='*' "$host:/mpac/sdicks02/repos/clasher-lease/jobs/" "reports/explore/search-ab/receipts/leased/$host/"
 rsync -ac "$host:/mpac/sdicks02/repos/clasher-lease/search-ab-runtime/reports/explore/search-ab/receipts/runtime-pin.json" "reports/explore/search-ab/receipts/leased/$host/runtime-pin.json"
done

mkdir -p reports/explore/search-ab/receipts/home08
rsync -ac --include="cpu-search-ab-*.log" --include="cpu-search-ab-*.exit" --include="cpu-search-ab-*.pid" --exclude="*" 127x08:/mpac/sdicks02/jobs/clasher/ reports/explore/search-ab/receipts/home08/
