#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

checkpoint_root=checkpoints/hog26_fresh_structured_dagger_seed1079501/train
report_root=reports/hog26_fresh_structured_dagger_seed1079501/milestones
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/validation.json
direct_parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
mkdir -p "$report_root"

for update in 5 10 20; do
  checkpoint="$checkpoint_root/policy_v2_update_$(printf '%06d' "$update").pt"
  while [[ ! -f "$checkpoint" ]]; do sleep 30; done
  sleep 2
  out="$report_root/u$update"
  mkdir -p "$out"
  typeset -a shared
  shared=(--checkpoint "$checkpoint" --decks-path decks.json \
    --sampling-decks-path "$opponent_decks" \
    --candidate-sampling-decks-path "$learner_decks" \
    --opponent-sampling-decks-path "$opponent_decks" \
    --decision-interval 8 --max-ticks 6000 --device cpu \
    --reward-profile objective-v1 --quiet-engine)
  nice -n 15 env PYTHONPATH=src:. OMP_NUM_THREADS=1 uv run python scripts/run_clasher.py eval -- \
    ${shared[@]} --opponent random --games 6 --seed 1071001 \
    --json-out "$out/random6.metrics.json" > "$out/random6.log" 2>&1
  nice -n 15 env PYTHONPATH=src:. OMP_NUM_THREADS=1 uv run python scripts/run_clasher.py eval -- \
    ${shared[@]} --opponent policy --opponent-checkpoint "$direct_parent" \
    --games 6 --seed 1071003 --json-out "$out/direct6.metrics.json" \
    > "$out/direct6.log" 2>&1
  nice -n 15 env PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/run_clasher.py strategy-benchmark -- \
    --checkpoint "$checkpoint" --decks-path decks.json \
    --sampling-decks-path "$opponent_decks" \
    --candidate-sampling-decks-path "$learner_decks" \
    --opponent-sampling-decks-path "$opponent_decks" \
    --games-per-opponent 2 --seed 1071002 --decision-interval 8 \
    --max-ticks 6000 --device cpu --reward-profile objective-v1 --quiet-engine \
    --json-out "$out/strategy.json" --markdown-out "$out/strategy.md" \
    > "$out/strategy.log" 2>&1
  print -r -- "fresh_structured_dagger_u${update}_complete_v1" > "$out/COMPLETE"
done
