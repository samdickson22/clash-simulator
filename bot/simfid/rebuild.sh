#!/usr/bin/env bash
# HF human-replay rebuild in our engine (bot/simfid/rebuild.py) for one engine tree + gamedata root.
#   bot/simfid/rebuild.sh SRC ROOT CROWN_FROM_GAMEDATA <rebuild.py args...>
# SRC: directory holding the `clasher` package; ROOT: CLASHER_ROOT (gamedata.json, hitboxes.json, pyproject.toml);
# CROWN: comma-separated spells whose pinned crown damage is dropped (live16402 roots: Fireball,Poison; else '').
set -euo pipefail
SRC=$1; ROOT=$2; CROWN=$3; shift 3
REPO=$(cd "$(dirname "$0")/../.." && pwd)
PY=${PY:-/mpac/sdicks02/repos/clasher/.venv/bin/python}
cd "$REPO"
CLASHER_ROOT=$ROOT SIMFID_CROWN_FROM_GAMEDATA=$CROWN PYTHONPATH=$SRC:$REPO PYTHONDONTWRITEBYTECODE=1 \
  OMP_NUM_THREADS=1 nice -n 15 "$PY" -m bot.simfid.rebuild "$@"
