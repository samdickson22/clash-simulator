#!/usr/bin/env bash
set -euo pipefail
cd /mpac/sdicks02/repos/clasher
host=${1:?host};target=${2:?target}
case "$host" in 127x03|127x09|127x13|127x14|127x15|127x16) ;; *) exit 2;; esac
ssh -o BatchMode=yes -o ConnectTimeout=10 "$host" "nice -n 10 chrt --idle 0 mkdir -p $target/reports/explore/tempo/receipts"
nice -n 10 chrt --idle 0 rsync --rsync-path='nice -n 10 chrt --idle 0 rsync' -acR src/clasher engine-rs/*.py engine-rs/clasher_core.abi3.so gamedata.json reports/strategy_council_20260928/engine-speed/es_common.py reports/strategy_council_20260928/engine-speed/stage5/fair_player.py reports/strategy_council_20260928/engine-speed/stage5/derived_public_state.py reports/strategy_council_20260928/search-noise-s6/delay.py reports/strategy_council_20260928/search-noise-s6/own_state.py reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json reports/strategy_council_20260928/m0/data/roles_v2/training.json reports/explore/search-ab/gpu_guard.py reports/explore/search-ab/case-costs.json reports/explore/tempo/worker_runtime.py reports/explore/tempo/exclusions.json reports/explore/tempo/case-costs.json reports/explore/tempo/audit_seeds.py tests/analysis/test_tempo.py "$host:$target/"
