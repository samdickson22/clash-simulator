#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

env \
  WORKERS="${WORKERS:-64}" \
  TRAIN_GAMES="${TRAIN_GAMES:-300}" \
  VALIDATION_GAMES="${VALIDATION_GAMES:-100}" \
  TRAIN_GAME_START="${TRAIN_GAME_START:-0}" \
  VALIDATION_GAME_START="${VALIDATION_GAME_START:-0}" \
  STATES_PER_GAME="${STATES_PER_GAME:-16}" \
  QUERY_STRIDE="${QUERY_STRIDE:-16}" \
  INCLUDE_STRUCTURED_STATE=1 \
  MINIMUM_TRAIN_ROOTS="${MINIMUM_TRAIN_ROOTS:-3500}" \
  MINIMUM_VALIDATION_ROOTS="${MINIMUM_VALIDATION_ROOTS:-1100}" \
  TRAIN_SEED="${TRAIN_SEED:-1169001}" \
  VALIDATION_SEED="${VALIDATION_SEED:-1172001}" \
  OUTPUT_ROOT="${OUTPUT_ROOT:-datasets/derived/hog26_structured_terminal_cf_probe_seed1169001}" \
  PYTHON_BIN="${PYTHON_BIN:-python}" \
  scripts/run_hog26_terminal_counterfactual_10k_seed1164601.sh
