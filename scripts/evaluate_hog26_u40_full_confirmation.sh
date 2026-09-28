#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/hog26_specialist_full_gate_seed1070501
out="$root/u40"
checkpoint=checkpoints/hog26_specialist_seed1070301/policy_v2_update_000040.pt
parent=checkpoints/fresh_f3_hazard_parentheavy_ab_seed1069901/plain/policy_v2_update_000028.pt
direct_parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
candidate_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/validation.json
corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz

for required in "$checkpoint" "$parent" "$direct_parent" "$candidate_decks" \
  "$opponent_decks" "$corpus" "$sidecar" "$root/parent/random24.metrics.json" \
  "$root/parent/direct24.metrics.json" "$root/parent/strategy.json"; do
  [[ -f "$required" ]] || { print -u2 -- "missing u40 confirmation input: $required"; exit 1; }
done
[[ ! -e "$out/COMPLETE" ]] || { print -u2 -- "refusing completed u40 confirmation"; exit 1; }
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
  --opponent-checkpoint "$direct_parent" --games 24 --seed 1070503 \
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
env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python \
  scripts/evaluate_recurrent_corpus.py --corpus "$corpus" \
  --public-observation-sidecar "$sidecar" --checkpoint "$parent" \
  --checkpoint "$checkpoint" --decks-path decks.json --max-episodes 128 \
  --episode-seed 1070505 --device cpu --json-out "$out/human128.json" \
  > "$out/human128.log" 2>&1
print -r -- 'hog26_u40_full_confirmation_complete_v1' > "$out/COMPLETE"
