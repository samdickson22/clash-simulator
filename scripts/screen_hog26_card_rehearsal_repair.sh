#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/hog26_card_rehearsal_repair_gameplay_seed1071001
candidate_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/validation.json
direct_parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
typeset -A checkpoints
checkpoints[u40]=checkpoints/hog26_specialist_seed1070301/policy_v2_update_000040.pt
checkpoints[u42]=checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000042.pt
checkpoints[u45]=checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000045.pt
checkpoints[u46]=checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt

for required in "$candidate_decks" "$opponent_decks" "$direct_parent" \
  ${checkpoints[@]}; do
  [[ -f "$required" ]] || { print -u2 -- "missing card-repair screen input: $required"; exit 1; }
done
[[ ! -e "$root/COMPLETE" ]] || { print -u2 -- "refusing completed card-repair screen"; exit 1; }
mkdir -p "$root"

evaluate_arm() {
  local arm=$1
  local checkpoint=$2
  local out="$root/$arm"
  mkdir -p "$out"
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
    uv run python run_clasher.py eval -- ${shared[@]} --opponent random \
    --games 12 --seed 1071001 --json-out "$out/random12.metrics.json" \
    > "$out/random12.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py eval -- ${shared[@]} --opponent policy \
    --opponent-checkpoint "$direct_parent" --games 12 --seed 1071003 \
    --json-out "$out/direct12.metrics.json" > "$out/direct12.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py strategy-benchmark -- \
    --checkpoint "$checkpoint" --decks-path decks.json \
    --sampling-decks-path "$opponent_decks" \
    --candidate-sampling-decks-path "$candidate_decks" \
    --opponent-sampling-decks-path "$opponent_decks" \
    --games-per-opponent 4 --seed 1071002 --decision-interval 8 --max-ticks 6000 \
    --device cpu --reward-profile objective-v1 --quiet-engine \
    --json-out "$out/strategy.json" --markdown-out "$out/strategy.md" \
    > "$out/strategy.log" 2>&1
}

typeset -a pids
pids=()
for arm checkpoint in ${(kv)checkpoints}; do
  evaluate_arm "$arm" "$checkpoint" &
  pids+=($!)
done
failed=0
for pid in $pids; do
  wait "$pid" || failed=1
done
(( failed == 0 )) || exit 1
print -r -- 'hog26_card_rehearsal_repair_gameplay_seed1071001_complete_v1' > "$root/COMPLETE"
