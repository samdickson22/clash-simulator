#!/usr/bin/env bash
set -euo pipefail
cd /mpac/sdicks02/repos/clasher
for host in 127x09 127x13 127x14 127x15; do
 nice -n 10 chrt --idle 0 rsync --rsync-path='nice -n 10 chrt --idle 0 rsync' -ac reports/explore/tempo/perception_rate.py "$host:/mpac/sdicks02/repos/clasher-lease/tempo-runtime/reports/explore/tempo/"
 ssh -o BatchMode=yes "$host" 'nice -n 10 chrt --idle 0 bash /mpac/sdicks02/repos/clasher-lease/run_v2.sh --max-processes 3 --expected-pss-gb 0.3 tempo-perception-rate-v1 -- nice -n 10 chrt --idle 0 /usr/bin/python3 -B /mpac/sdicks02/repos/clasher-lease/tempo-runtime/reports/explore/tempo/perception_rate.py --auto --out /mpac/sdicks02/repos/clasher-lease/tempo-runtime/reports/explore/tempo/receipts/perception-rate.jsonl' > "reports/explore/tempo/receipts/monitor-$host.json" 2>&1 || true
done
