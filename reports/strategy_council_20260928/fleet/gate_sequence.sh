#!/usr/bin/env bash
set -uo pipefail
result=0
fleet=reports/strategy_council_20260928/fleet
for suite in p16 c56 random; do
 bash "$fleet/fleet_run.sh" --worker "${suite}-linux-20261007" bash "$fleet/identity.sh" "$suite" linux-20261007 >> "/mpac/sdicks02/jobs/clasher/${suite}-linux-20261007.log" 2>&1 || result=1
done
for suite in fast stage2 stage4 stage5 stage5-replay speed; do
 bash "$fleet/fleet_run.sh" --worker "${suite}-linux-20261007" bash "$fleet/regressions.sh" "$suite" >> "/mpac/sdicks02/jobs/clasher/${suite}-linux-20261007.log" 2>&1 || result=1
done
exit "$result"
