#!/usr/bin/env bash
# T1 native-fixture fidelity (bot/fidelity) for one engine tree + gamedata root.
#   bot/simfid/t1.sh OUT SRC ROOT [CROWN_FROM_GAMEDATA] [WORKERS]
# SRC: directory holding the `clasher` package; ROOT: CLASHER_ROOT (gamedata.json, hitboxes.json, pyproject.toml).
set -euo pipefail
OUT=$1; SRC=$2; ROOT=$3; CROWN=${4:-}; WORKERS=${5:-40}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
PY=${PY:-/mpac/sdicks02/repos/clasher/.venv/bin/python}
DATA=${T1_DATA:-/mpac/sdicks02/repos/clasher-bot-data}
cd "$REPO"
CLASHER_ROOT=$ROOT SIMFID_CROWN_FROM_GAMEDATA=$CROWN PYTHONPATH=$SRC:$REPO PYTHONDONTWRITEBYTECODE=1 \
  nice -n 15 "$PY" -m bot.fidelity.run --engine clasher --data "$DATA/t1-trainval" --split "$DATA/t1-split.json" \
  --ids bot/fidelity/c56_native_ids.json --out "$OUT" --workers "$WORKERS" --issue-offset -1
CLASHER_ROOT=$ROOT PYTHONPATH=$SRC:$REPO "$PY" -m bot.fidelity.aggregate "$OUT" --json "$OUT/aggregate-all.json"
