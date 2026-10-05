#!/usr/bin/env bash

set -euo pipefail

desktop_root=${DESKTOP_ROOT:-/Users/sam/Desktop/code/clasher}
out=${OUTPUT_ROOT:-/Users/sam/.codex/worktrees/clasher-simple-mps-bench/reports/hog26_parent_stochasticity_seed1192301}
checkpoint=$desktop_root/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt
candidate_decks=$desktop_root/training_decks/katacr_hog26_only.json
opponent_decks=$desktop_root/datasets/deck_curriculum_v3_seed1056101/heldout_action_value_screen_clean_seed1164811.json
python_bin=$desktop_root/.venv/bin/python

for required in "$checkpoint" "$candidate_decks" "$opponent_decks" "$python_bin"; do
  [[ -e "$required" ]] || { echo "missing stochasticity input: $required" >&2; exit 1; }
done
[[ ! -f "$out/COMPLETE" ]] || { echo "stochasticity audit already complete" >&2; exit 1; }
mkdir -p "$out"

run_eval() {
  local arm=$1
  local opponent=$2
  local seed=$3
  local opponent_args=()
  if [[ "$opponent" == random ]]; then
    opponent_args=(--opponent random)
  else
    opponent_args=(--opponent strategy --opponent-strategy "$opponent")
  fi
  cd "$desktop_root"
  local command=(
    nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1
    "$python_bin" scripts/run_clasher.py eval --
    --checkpoint "$checkpoint" --decks-path decks.json \
    --sampling-decks-path "$opponent_decks" \
    --candidate-sampling-decks-path "$candidate_decks" \
    --opponent-sampling-decks-path "$opponent_decks" \
    --decision-interval 8 --max-ticks 6000 --device cpu \
    --reward-profile objective-v1 --quiet-engine --games 6 --seed "$seed" \
    --json-out "$out/$arm-$opponent.metrics.json"
    --games-json-out "$out/$arm-$opponent.games.json"
  )
  [[ "$arm" == stochastic ]] && command+=(--stochastic)
  command+=("${opponent_args[@]}")
  "${command[@]}" > "$out/$arm-$opponent.log" 2>&1
}

for arm in deterministic stochastic; do
  run_eval "$arm" balanced 1192301
  run_eval "$arm" random 1192302
done

printf '%s\n' hog26_parent_stochasticity_seed1192301_complete_v1 > "$out/COMPLETE"
