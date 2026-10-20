#!/usr/bin/env bash
# LIVE-recording fidelity for one engine tree + gamedata root.
#   bot/simfid/live.sh OUT SRC ROOT [CROWN_FROM_GAMEDATA] [extra live_run args...]
set -euo pipefail
OUT=$1; SRC=$2; ROOT=$3; CROWN=${4:-}; shift 4 || shift $#
REPO=$(cd "$(dirname "$0")/../.." && pwd)
PY=${PY:-/mpac/sdicks02/repos/clasher/.venv/bin/python}
cd "$REPO"
CLASHER_ROOT=$ROOT SIMFID_CROWN_FROM_GAMEDATA=$CROWN PYTHONPATH=$SRC:$REPO PYTHONDONTWRITEBYTECODE=1 \
  nice -n 15 "$PY" -m bot.simfid.live_run --out "$OUT" "$@"
