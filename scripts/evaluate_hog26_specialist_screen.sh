#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/hog26_specialist_screen_seed1070401
candidate_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/pfsp_tuning_strict_v2_holdouts.json
direct_parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
typeset -A checkpoints
checkpoints[parent]=checkpoints/fresh_f3_hazard_parentheavy_ab_seed1069901/plain/policy_v2_update_000028.pt
checkpoints[u32]=checkpoints/hog26_specialist_seed1070301/policy_v2_update_000032.pt
checkpoints[u36]=checkpoints/hog26_specialist_seed1070301/policy_v2_update_000036.pt
checkpoints[u40]=checkpoints/hog26_specialist_seed1070301/policy_v2_update_000040.pt

for required in "$candidate_decks" "$opponent_decks" "$direct_parent" \
  ${checkpoints[@]}; do
  [[ -f "$required" ]] || { print -u2 -- "missing Hog screen input: $required"; exit 1; }
done
[[ ! -e "$root/COMPLETE" ]] || { print -u2 -- "refusing completed screen"; exit 1; }
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
    uv run python scripts/run_clasher.py eval -- ${shared[@]} --opponent random \
    --games 12 --seed 1070401 --json-out "$out/random12.metrics.json" \
    --games-json-out "$out/random12.games.json" > "$out/random12.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/run_clasher.py eval -- ${shared[@]} --opponent strategy \
    --opponent-strategy balanced --games 6 --seed 1070402 \
    --json-out "$out/balanced6.metrics.json" \
    --games-json-out "$out/balanced6.games.json" > "$out/balanced6.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/run_clasher.py eval -- ${shared[@]} --opponent strategy \
    --opponent-strategy reactive-defense --games 6 --seed 1070403 \
    --json-out "$out/reactive6.metrics.json" \
    --games-json-out "$out/reactive6.games.json" > "$out/reactive6.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/run_clasher.py eval -- ${shared[@]} --opponent policy \
    --opponent-checkpoint "$direct_parent" --games 12 --seed 1070404 \
    --json-out "$out/direct12.metrics.json" \
    --games-json-out "$out/direct12.games.json" > "$out/direct12.log" 2>&1
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
print -r -- 'hog26_specialist_screen_seed1070401_complete_v1' > "$root/COMPLETE"
