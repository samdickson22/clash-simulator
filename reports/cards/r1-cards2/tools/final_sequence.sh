#!/usr/bin/env bash
# Accurate leases for the final stages (assemble/smoke 1, HEADLINE 8, totality 4).
set -euo pipefail
J=/mpac/sdicks02/jobs/clasher/cards/r1-cards2/final
RUN=$J/repo/reports/cards/r1-cards2/tools/finalize.sh
CPU=/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh
for spec in assemble:1 smoke:1 k4l-full:8 totality:4; do
  "$CPU" "${spec#*:}" nice -n 15 bash "$RUN" "${spec%%:*}"
done
touch "$J/all.done"
