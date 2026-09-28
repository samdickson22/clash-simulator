#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-python}
output_root=${OUTPUT_ROOT:-reports/hog26_overtime_schedule_canary_seed1175001}
games=${GAMES:-"2 8 14 16 17 20 32 41 59 60 61 62"}
mkdir -p "$output_root"

run_game() {
  local game=$1
  local padded
  padded=$(printf '%06d' "$game")
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    "$python_bin" scripts/collect_terminal_counterfactual_corpus.py \
      --policy checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt \
      --decks-path decks.json \
      --learner-sampling-decks-path training_decks/katacr_hog26_only.json \
      --opponent-sampling-decks-path datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json \
      --games 1 --game-offset "$game" --seed 1175001 \
      --states-per-game 16 --minimum-tick 256 --query-stride 16 \
      --query-schedule phase-balanced --decision-interval 8 --max-ticks 6000 \
      --max-candidates 6 --locations-per-slot 1 \
      --include-structured-state --include-action-time-recurrent-state \
      --device cpu --torch-threads 1 \
      --output "$output_root/game_${padded}.npz" \
      --report "$output_root/game_${padded}.json" \
      > "$output_root/game_${padded}.log" 2>&1
}

pids=()
for game in $games; do
  run_game "$game" &
  pids+=("$!")
done
failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || failed=1
done
((failed == 0)) || exit 1
printf '%s\n' 'hog26_overtime_schedule_canary_seed1175001_complete_v1' \
  > "$output_root/COMPLETE"
