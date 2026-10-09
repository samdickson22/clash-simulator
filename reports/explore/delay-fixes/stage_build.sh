#!/usr/bin/env bash
set -euo pipefail
root=/mpac/sdicks02/repos/clasher-lease/delay-fixes-runtime
host=${1:-127x13}
ssh -o BatchMode=yes -o ConnectTimeout=10 "$host" "mkdir -p $root"
rsync -acR src/clasher engine-rs/src engine-rs/Cargo.toml engine-rs/Cargo.lock engine-rs/build.sh engine-rs/*.py gamedata.json reports/strategy_council_20260928/engine-speed/es_common.py reports/strategy_council_20260928/engine-speed/stage5/fair_player.py reports/strategy_council_20260928/engine-speed/stage5/derived_public_state.py reports/strategy_council_20260928/search-noise-s6/delay.py reports/strategy_council_20260928/search-noise-s6/own_state.py reports/explore/loss-review/seeds.json "$host:$root/"
ssh -o BatchMode=yes "$host" "cd /mpac/sdicks02/repos/clasher-lease/search-ab-runtime && cp --parents reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json reports/strategy_council_20260928/m0/data/roles_v2/training.json $root/"
ssh -o BatchMode=yes "$host" "bash /mpac/sdicks02/repos/clasher-lease/run_v2.sh --max-processes 8 --expected-pss-gb 4 cpu-delay-fixes-build-v1 -- /usr/bin/env CARGO_TARGET_DIR=/mpac/sdicks02/repos/clasher-lease/build/delay-fixes-v1 PYO3_PYTHON=/mpac/sdicks02/repos/clasher-lease/repo/.venv/bin/python /bin/bash $root/engine-rs/build.sh"
