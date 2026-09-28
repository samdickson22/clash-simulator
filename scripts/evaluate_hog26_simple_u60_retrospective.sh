#!/usr/bin/env bash

set -euo pipefail

desktop_root=${DESKTOP_ROOT:-/Users/sam/Desktop/code/clasher}
simple_root=${SIMPLE_ROOT:-/Users/sam/.codex/worktrees/clasher-simple-mps-bench}
out=${OUTPUT_ROOT:-$simple_root/reports/hog26_simple_heterogeneous_seed1164301/development_retrospective_u60}
parent=${PARENT:-$desktop_root/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt}
candidate=${CANDIDATE:-$simple_root/checkpoints/hog26_simple_heterogeneous_seed1164301/policy_v2_update_000060.pt}
candidate_decks=$desktop_root/training_decks/katacr_hog26_only.json
opponents=$desktop_root/datasets/deck_curriculum_v3_seed1056101/heldout_action_value_screen_clean_seed1164811.json
python_bin=$desktop_root/.venv/bin/python

for required in "$parent" "$candidate" "$candidate_decks" "$opponents" "$python_bin"; do
  [[ -e "$required" ]] || { echo "missing retrospective input: $required" >&2; exit 1; }
done
[[ ! -f "$out/COMPLETE" ]] || { echo "retrospective already complete" >&2; exit 1; }
mkdir -p "$out"

run_eval() {
  local checkpoint=$1
  local arm=$2
  local opponent=$3
  local seed=$4
  local opponent_args=()
  if [[ "$opponent" == random ]]; then
    opponent_args=(--opponent random)
  else
    opponent_args=(--opponent strategy --opponent-strategy "$opponent")
  fi
  cd "$desktop_root"
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    "$python_bin" run_clasher.py eval -- \
    --checkpoint "$checkpoint" --decks-path decks.json \
    --sampling-decks-path "$opponents" \
    --candidate-sampling-decks-path "$candidate_decks" \
    --opponent-sampling-decks-path "$opponents" \
    --decision-interval 8 --max-ticks 6000 --device cpu \
    --reward-profile objective-v1 --quiet-engine --games 4 --seed "$seed" \
    --json-out "$out/$arm-$opponent.metrics.json" \
    --games-json-out "$out/$arm-$opponent.games.json" \
    "${opponent_args[@]}" > "$out/$arm-$opponent.log" 2>&1
}

for arm in parent candidate; do
  checkpoint=$parent
  [[ "$arm" == candidate ]] && checkpoint=$candidate
  run_eval "$checkpoint" "$arm" balanced 1192601
  run_eval "$checkpoint" "$arm" bridge-pressure 1192602
  run_eval "$checkpoint" "$arm" random 1192603
done

printf '%s\n' hog26_simple_heterogeneous_u60_retrospective_complete_v1 > "$out/COMPLETE"
