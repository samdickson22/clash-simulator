#!/usr/bin/env bash
# X4S2 on 127x03 after the 07:28Z extension: when rep03C exits, run phases E/F (rep03EF, plan-ext.json) to 13:30Z.
set -u
J=/mpac/sdicks02/jobs/clasher/x4s2-20261011; R=$J/repo/reports/explore/x4s2
cd $J
until [ -e rep03C/supervisor-exit.json ]; do [ -e STOP ] && exit 0; sleep 10; done
[ -e STOP ] && exit 0
[ "$(date -u +%H%M)" -ge 1320 ] && exit 0
bash $R/runtime.sh reports/explore/x4s2/supervise.py --job $J --phase rep03EF --worklist $R/wl-03EF.json --config $R/plan-ext.json --stop-at 2026-10-11T13:30:00Z
