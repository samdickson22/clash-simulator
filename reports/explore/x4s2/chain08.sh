#!/usr/bin/env bash
# X4S2 on 127x08 after the coordinator's 07:28Z extension: when rep08 (stop-at 09:15Z) exits, run its never-started
# blocks (rep08L, committed phases B/D), then phases E/F (rep08EF, plan-ext.json); all stop-at 12:15Z. STOP overrides.
set -u
J=/mpac/sdicks02/jobs/clasher/x4s2-20261011; R=$J/repo/reports/explore/x4s2
cd $J
until [ -e rep08/supervisor-exit.json ]; do [ -e STOP ] && exit 0; sleep 10; done
[ -e STOP ] && exit 0
[ "$(date -u +%H%M)" -ge 1205 ] && exit 0
python3 $R/leftover.py $R/wl-08.json rep08 logs/wl-08L.json > logs/leftover-08.json
if python3 -c "import json,sys;sys.exit(0 if json.load(open('logs/wl-08L.json'))['blocks'] else 1)"; then
  bash $R/runtime.sh reports/explore/x4s2/supervise.py --job $J --phase rep08L --worklist $J/logs/wl-08L.json --stop-at 2026-10-11T12:15:00Z
fi
[ -e STOP ] && exit 0
bash $R/runtime.sh reports/explore/x4s2/supervise.py --job $J --phase rep08EF --worklist $R/wl-08EF.json --config $R/plan-ext.json --stop-at 2026-10-11T12:15:00Z
