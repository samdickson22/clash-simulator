#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

experiment_seed=${EXPERIMENT_SEED:-1081201}
gate_seed_base=${GATE_SEED_BASE:-$((experiment_seed + 100))}
checkpoint_root=checkpoints/hog26_simultaneous_dualsource_hazard_seed${experiment_seed}/train
report_root=reports/hog26_simultaneous_dualsource_hazard_seed${experiment_seed}/milestones
mkdir -p "$report_root"

for update in 10 20; do
  padded=$(printf '%06d' "$update")
  checkpoint="$checkpoint_root/policy_v2_update_${padded}.pt"
  root="$report_root/u${update}"
  mkdir -p "$root"
  while [[ ! -f "$checkpoint" ]]; do sleep 5; done
  common=(
    --checkpoint "$checkpoint"
    --decks-path decks.json
    --sampling-decks-path datasets/deck_curriculum_v3_seed1056101/validation.json
    --candidate-sampling-decks-path training_decks/katacr_hog26_only.json
    --opponent-sampling-decks-path datasets/deck_curriculum_v3_seed1056101/validation.json
    --decision-interval 8 --max-ticks 6000 --device cpu
    --reward-profile objective-v1 --quiet-engine
  )
  seed=$((gate_seed_base + update * 10))
  env OMP_NUM_THREADS=2 PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    "${common[@]}" --opponent random --games 6 --seed "$seed" \
    --json-out "$root/random6.json" > "$root/random6.log" 2>&1
  env OMP_NUM_THREADS=2 PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    "${common[@]}" --opponent policy \
    --opponent-checkpoint checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt \
    --games 6 --seed $((seed + 2)) --json-out "$root/direct6.json" \
    > "$root/direct6.log" 2>&1
  env OMP_NUM_THREADS=2 PYTHONPATH=src:. uv run python run_clasher.py strategy-benchmark -- \
    "${common[@]}" --games-per-opponent 2 --seed $((seed + 1)) \
    --json-out "$root/strategy.json" --markdown-out "$root/strategy.md" \
    > "$root/strategy.log" 2>&1
  print -r -- COMPLETE > "$root/COMPLETE"
done
