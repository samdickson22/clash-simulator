#!/usr/bin/env bash
set -euo pipefail
cd /mpac/sdicks02/repos/clasher
remote=/mpac/sdicks02/repos/clasher/reports/explore/search-ab/runtime-v2
ssh -o BatchMode=yes 127x08 "mkdir -p $remote/reports/explore/search-ab/shards"
rsync -acR src/clasher engine-rs/*.py engine-rs/clasher_core.abi3.so gamedata.json reports/strategy_council_20260928/engine-speed/es_common.py reports/strategy_council_20260928/engine-speed/stage5/fair_player.py reports/strategy_council_20260928/engine-speed/stage5/derived_public_state.py reports/strategy_council_20260928/search-noise-s6/delay.py reports/strategy_council_20260928/search-noise-s6/own_state.py reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json reports/strategy_council_20260928/m0/data/roles_v2/training.json reports/explore/search-ab/exclusions.json reports/explore/search-ab/home_worker.py reports/explore/search-ab/worker_runtime.py reports/explore/search-ab/gpu_guard.py reports/explore/search-ab/coexistence.py reports/explore/search-ab/case-costs.json "127x08:$remote/"
