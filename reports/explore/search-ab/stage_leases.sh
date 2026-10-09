#!/usr/bin/env bash
set -euo pipefail
cd /mpac/sdicks02/repos/clasher
for host in 127x09 127x14 127x16; do
 ssh -o BatchMode=yes -o ConnectTimeout=10 "$host" 'mkdir -p /mpac/sdicks02/repos/clasher-lease/search-ab-runtime-v2/reports/explore/search-ab/receipts'
 rsync -acR src/clasher engine-rs/*.py engine-rs/clasher_core.abi3.so gamedata.json reports/strategy_council_20260928/engine-speed/es_common.py reports/strategy_council_20260928/engine-speed/stage5/fair_player.py reports/strategy_council_20260928/engine-speed/stage5/derived_public_state.py reports/strategy_council_20260928/search-noise-s6/delay.py reports/strategy_council_20260928/search-noise-s6/own_state.py reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json reports/strategy_council_20260928/m0/data/roles_v2/training.json reports/explore/search-ab/exclusions.json reports/explore/search-ab/lease_worker.py reports/explore/search-ab/worker_runtime.py reports/explore/search-ab/gpu_guard.py reports/explore/search-ab/case-costs.json "$host:/mpac/sdicks02/repos/clasher-lease/search-ab-runtime-v2/"
 ssh -o BatchMode=yes "$host" 'nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader'
 echo "staged $host"
done
