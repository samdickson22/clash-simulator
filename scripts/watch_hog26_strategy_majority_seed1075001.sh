#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

checkpoint_root=checkpoints/hog26_strategy_majority_seed1075001
report_root=reports/hog26_strategy_majority_milestones_seed1075101
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/validation.json
direct_parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt

mkdir -p "$report_root"

wait_for_checkpoint() {
  local checkpoint=$1
  while [[ ! -f "$checkpoint" ]]; do
    sleep 30
  done
  local before after
  before=$(stat -f%z "$checkpoint")
  sleep 2
  after=$(stat -f%z "$checkpoint")
  [[ "$before" == "$after" ]] || { sleep 5; wait_for_checkpoint "$checkpoint"; }
}

for update in 56 66 86 106 126 146; do
  checkpoint="$checkpoint_root/policy_v2_update_$(printf '%06d' "$update").pt"
  out="$report_root/u$update"
  wait_for_checkpoint "$checkpoint"
  [[ -f "$out/COMPLETE" ]] && continue
  mkdir -p "$out"
  typeset -a shared
  shared=(
    --checkpoint "$checkpoint" --decks-path decks.json
    --sampling-decks-path "$opponent_decks"
    --candidate-sampling-decks-path "$learner_decks"
    --opponent-sampling-decks-path "$opponent_decks"
    --decision-interval 8 --max-ticks 6000 --device cpu
    --reward-profile objective-v1 --quiet-engine
  )
  nice -n 15 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py eval -- ${shared[@]} --opponent random \
    --games 12 --seed 1071001 --json-out "$out/random12.metrics.json" \
    > "$out/random12.log" 2>&1
  nice -n 15 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py eval -- ${shared[@]} --opponent policy \
    --opponent-checkpoint "$direct_parent" --games 12 --seed 1071003 \
    --json-out "$out/direct12.metrics.json" > "$out/direct12.log" 2>&1
  nice -n 15 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py strategy-benchmark -- \
    --checkpoint "$checkpoint" --decks-path decks.json \
    --sampling-decks-path "$opponent_decks" \
    --candidate-sampling-decks-path "$learner_decks" \
    --opponent-sampling-decks-path "$opponent_decks" \
    --games-per-opponent 4 --seed 1071002 --decision-interval 8 \
    --max-ticks 6000 --device cpu --reward-profile objective-v1 --quiet-engine \
    --json-out "$out/strategy.json" --markdown-out "$out/strategy.md" \
    > "$out/strategy.log" 2>&1
  print -r -- "hog26_strategy_majority_milestone_u${update}_complete_v1" > "$out/COMPLETE"
done

print -r -- 'hog26_strategy_majority_milestones_seed1075101_complete_v1' > "$report_root/COMPLETE"
