#!/usr/bin/env bash
set -euo pipefail
fleet=reports/strategy_council_20260928/fleet
.venv/bin/python -B "$fleet/recorded_parallel.py"
bash "$fleet/identity.sh" recorded linux-20261007
