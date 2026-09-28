#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/hog26_specialist_full_gate_seed1070501
candidate_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/validation.json
corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz
typeset -A checkpoints
checkpoints[parent]=checkpoints/fresh_f3_hazard_parentheavy_ab_seed1069901/plain/policy_v2_update_000028.pt
checkpoints[candidate]=checkpoints/hog26_specialist_seed1070301/policy_v2_update_000036.pt

for required in "$candidate_decks" "$opponent_decks" "$corpus" "$sidecar" \
  ${checkpoints[@]}; do
  [[ -f "$required" ]] || { print -u2 -- "missing full Hog gate input: $required"; exit 1; }
done
[[ -f reports/hog26_specialist_screen_seed1070401/COMPLETE ]] || {
  print -u2 -- "matched Hog checkpoint screen is incomplete"
  exit 1
}
[[ ! -e "$root/COMPLETE" ]] || { print -u2 -- "refusing completed full gate"; exit 1; }
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
    --games 24 --seed 1070501 --json-out "$out/random24.metrics.json" \
    --games-json-out "$out/random24.games.json" > "$out/random24.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py strategy-benchmark -- \
    --checkpoint "$checkpoint" --decks-path decks.json \
    --sampling-decks-path "$opponent_decks" \
    --candidate-sampling-decks-path "$candidate_decks" \
    --opponent-sampling-decks-path "$opponent_decks" \
    --games-per-opponent 4 --seed 1070502 --decision-interval 8 --max-ticks 6000 \
    --device cpu --reward-profile objective-v1 --quiet-engine \
    --json-out "$out/strategy.json" --markdown-out "$out/strategy.md" \
    > "$out/strategy.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py eval -- ${shared[@]} --opponent policy \
    --opponent-checkpoint "${checkpoints[parent]}" --games 24 --seed 1070503 \
    --json-out "$out/direct24.metrics.json" \
    --games-json-out "$out/direct24.games.json" > "$out/direct24.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py eval -- ${shared[@]} --opponent strategy \
    --opponent-strategy balanced --games 12 --seed 1070504 \
    --json-out "$out/utilization12.metrics.json" \
    --games-json-out "$out/utilization12.games.json" \
    --decisions-json-out "$out/utilization12.decisions.json" \
    > "$out/utilization12.log" 2>&1
  env PYTHONPATH=src:. uv run python scripts/evaluate_win_condition_utilization.py \
    --decisions "$out/utilization12.decisions.json" \
    --games "$out/utilization12.games.json" --card HogRider \
    --max-zero-use-rate 0.10 --min-window-conversion-rate 0.25 \
    --min-games-per-seat 5 --json-out "$out/utilization.json" \
    > "$out/utilization_audit.log" 2>&1
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

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python \
  scripts/evaluate_recurrent_corpus.py --corpus "$corpus" \
  --public-observation-sidecar "$sidecar" --checkpoint "${checkpoints[parent]}" \
  --checkpoint "${checkpoints[candidate]}" --decks-path decks.json \
  --max-episodes 128 --episode-seed 1070505 --device cpu \
  --json-out "$root/human128.json" > "$root/human128.log" 2>&1

print -r -- 'hog26_specialist_full_gate_seed1070501_complete_v1' > "$root/COMPLETE"
