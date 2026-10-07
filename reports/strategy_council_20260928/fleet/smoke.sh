#!/usr/bin/env bash
set -euo pipefail
fleet=reports/strategy_council_20260928/fleet
.venv/bin/python -B "$fleet/verify_inputs.py"
.venv/bin/python -c 'import sys,clasher_core; print(sys.version); print(clasher_core.__file__)'
bash "$fleet/identity.sh" p16 smoke-20261007
