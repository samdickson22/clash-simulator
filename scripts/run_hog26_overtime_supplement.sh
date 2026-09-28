#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-python}
workers=${WORKERS:-64}
screen_manifest=${SCREEN_MANIFEST:?SCREEN_MANIFEST is required}
opponent_decks=${OPPONENT_DECKS:?OPPONENT_DECKS is required}
selected_count=${SELECTED_COUNT:?SELECTED_COUNT is required}
seed=${SEED:?SEED is required}
output_root=${OUTPUT_ROOT:?OUTPUT_ROOT is required}
policy=${POLICY:-checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt}
learner_decks=${LEARNER_DECKS:-training_decks/katacr_hog26_only.json}

mkdir -p "$output_root/shards"
selection_file=$(mktemp "$output_root/.selected_games_XXXXXX")
trap 'rm -f "$selection_file"' EXIT
env PYTHONPATH=src:. "$python_bin" \
  scripts/validate_hog26_overtime_screen_manifest.py \
    --manifest "$screen_manifest" \
    --policy "$policy" \
    --learner-decks "$learner_decks" \
    --opponent-decks "$opponent_decks" \
    --selected-count "$selected_count" \
    > "$selection_file"
selected_games=()
while IFS= read -r game; do
  [[ -n "$game" ]] && selected_games+=("$game")
done < "$selection_file"
rm -f "$selection_file"
trap - EXIT

collect_game() {
  local game=$1
  local padded partial
  padded=$(printf '%06d' "$game")
  if [[ -f "$output_root/shards/game_${padded}.npz" && \
        -f "$output_root/shards/game_${padded}.json" ]]; then
    return 0
  fi
  partial=$(mktemp -d "$output_root/shards/.partial_${padded}_XXXXXX")
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    "$python_bin" scripts/collect_terminal_counterfactual_corpus.py \
      --policy "$policy" --decks-path decks.json \
      --learner-sampling-decks-path "$learner_decks" \
      --opponent-sampling-decks-path "$opponent_decks" \
      --games 1 --game-offset "$game" --seed "$seed" \
      --states-per-game 1 --minimum-tick 3600 --query-stride 1 \
      --query-schedule phase-balanced --decision-interval 8 --max-ticks 6000 \
      --max-candidates 6 --locations-per-slot 1 \
      --include-structured-state --include-action-time-recurrent-state \
      --device cpu --torch-threads 1 \
      --output "$partial/shard.npz" --report "$partial/shard.json" \
      > "$partial/shard.log" 2>&1
  mv "$partial/shard.npz" "$output_root/shards/game_${padded}.npz"
  mv "$partial/shard.json" "$output_root/shards/game_${padded}.json"
  mv "$partial/shard.log" "$output_root/shards/game_${padded}.log"
  rmdir "$partial"
}

failed=0
if help wait 2>/dev/null | grep -q -- '-n'; then
  active=0
  for game in "${selected_games[@]}"; do
    collect_game "$game" &
    active=$((active + 1))
    if ((active >= workers)); then
      wait -n || failed=1
      active=$((active - 1))
    fi
  done
  while ((active > 0)); do
    wait -n || failed=1
    active=$((active - 1))
  done
else
  lanes=$workers
  ((${#selected_games[@]} < lanes)) && lanes=${#selected_games[@]}
  pids=()
  for ((worker = 0; worker < lanes; worker++)); do
    (
      for ((index = worker; index < ${#selected_games[@]}; index += lanes)); do
        collect_game "${selected_games[index]}"
      done
    ) &
    pids+=("$!")
  done
  for pid in "${pids[@]}"; do
    wait "$pid" || failed=1
  done
fi
((failed == 0)) || exit 1

env PYTHONPATH=src:. "$python_bin" \
  scripts/combine_terminal_counterfactual_corpora.py \
    --input-root "$output_root/shards" \
    --output "$output_root/combined.npz" \
    --report "$output_root/combined.json"

printf '%s\n' 'hog26_overtime_supplement_complete_v1' > "$output_root/COMPLETE"
