#!/usr/bin/env bash
set -euo pipefail
cd /mpac/sdicks02/repos/clasher
[[ -f /mpac/sdicks02/jobs/clasher/transfer-ready.json ]]
es=reports/strategy_council_20260928/engine-speed
out=/mpac/sdicks02/jobs/clasher
mode=${1:?p16 c56 recorded random}; label=${2:?label}
export CLASHER_ROOT="$PWD" PYTHONPATH="$PWD/src" PYTHONDONTWRITEBYTECODE=1
case "$mode" in
 p16) .venv/bin/python -B reports/strategy_council_20260928/c56/engine/tools/p16_identity.py check reports/strategy_council_20260928/c56/engine/p16_identity_baseline_admitted.json ;;
 c56) .venv/bin/python -B "$es/c56_identity.py" check "$es/c56_identity_baseline_canonical.json" ;;
 recorded|random) .venv/bin/python -B "$es/broad_identity.py" "$mode" check "$es/${mode}_identity_baseline_admitted.json" --output "$out/${mode}_${label}.json" ;;
 *) exit 2 ;;
esac
