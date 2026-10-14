#!/usr/bin/env bash
# Light, single-thread, deterministic-env launcher for bot.players (127x05-safe).
#   bot/players/run.sh -m bot.players.smoke --ticks 1200
# CLASHER_BOT_RUNTIME overrides the read-only runtime root (see runtime.py).
# BOT_CPU pins to one core (default 2); nice 19 always.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
export CUDA_VISIBLE_DEVICES='' PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
cd "$repo"
exec nice -n 19 taskset -c "${BOT_CPU:-2}" "$repo/.venv/bin/python" -B "$@"
