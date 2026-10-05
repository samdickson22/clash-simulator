#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

baseline_root=reports/hog26_specialist_full_gate_seed1070501/u40
root=reports/hog26_card_rehearsal_repair_gate_seed1070901/u46_full
checkpoint=checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt
direct_parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
candidate_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/validation.json

for required in "$checkpoint" "$direct_parent" "$candidate_decks" \
  "$opponent_decks" "$baseline_root/random24.metrics.json" \
  "$baseline_root/direct24.metrics.json" "$baseline_root/strategy.json" \
  "$baseline_root/utilization.json"; do
  [[ -f "$required" ]] || { print -u2 -- "missing u46 confirmation input: $required"; exit 1; }
done
[[ ! -e "$root/COMPLETE" ]] || { print -u2 -- "refusing completed u46 confirmation"; exit 1; }
mkdir -p "$root"
typeset -a shared
shared=(
  --checkpoint "$checkpoint" --decks-path decks.json
  --sampling-decks-path "$opponent_decks"
  --candidate-sampling-decks-path "$candidate_decks"
  --opponent-sampling-decks-path "$opponent_decks"
  --decision-interval 8 --max-ticks 6000 --device cpu
  --reward-profile objective-v1 --quiet-engine
)

nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python scripts/run_clasher.py eval -- ${shared[@]} --opponent random \
  --games 24 --seed 1070501 --json-out "$root/random24.metrics.json" \
  --games-json-out "$root/random24.games.json" > "$root/random24.log" 2>&1
nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python scripts/run_clasher.py strategy-benchmark -- \
  --checkpoint "$checkpoint" --decks-path decks.json \
  --sampling-decks-path "$opponent_decks" \
  --candidate-sampling-decks-path "$candidate_decks" \
  --opponent-sampling-decks-path "$opponent_decks" \
  --games-per-opponent 4 --seed 1070502 --decision-interval 8 --max-ticks 6000 \
  --device cpu --reward-profile objective-v1 --quiet-engine \
  --json-out "$root/strategy.json" --markdown-out "$root/strategy.md" \
  > "$root/strategy.log" 2>&1
nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python scripts/run_clasher.py eval -- ${shared[@]} --opponent policy \
  --opponent-checkpoint "$direct_parent" --games 24 --seed 1070503 \
  --json-out "$root/direct24.metrics.json" \
  --games-json-out "$root/direct24.games.json" > "$root/direct24.log" 2>&1
nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python scripts/run_clasher.py eval -- ${shared[@]} --opponent strategy \
  --opponent-strategy balanced --games 12 --seed 1070504 \
  --json-out "$root/utilization12.metrics.json" \
  --games-json-out "$root/utilization12.games.json" \
  --decisions-json-out "$root/utilization12.decisions.json" \
  > "$root/utilization12.log" 2>&1
env PYTHONPATH=src:. uv run python scripts/evaluate_win_condition_utilization.py \
  --decisions "$root/utilization12.decisions.json" \
  --games "$root/utilization12.games.json" --card HogRider \
  --max-zero-use-rate 0.10 --min-window-conversion-rate 0.25 \
  --min-games-per-seat 5 --json-out "$root/utilization.json" \
  > "$root/utilization_audit.log" 2>&1
print -r -- 'hog26_u46_full_confirmation_complete_v1' > "$root/COMPLETE"
