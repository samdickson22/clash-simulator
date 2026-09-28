#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/fresh_f3_hazard_mixed_league_gate_seed1068801
parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
candidate=checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000030.pt
development=datasets/deck_curriculum_v3_seed1056101/pfsp_tuning_strict_v2_holdouts.json
validation=datasets/deck_curriculum_v3_seed1056101/validation.json
corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz
parent_root=reports/fresh_f3_hazard_fullweight_update20_seed1068601/candidate

for required in "$parent" "$candidate" "$corpus" "$sidecar" \
  "$parent_root/strategy.json" "$parent_root/random24.metrics.json" \
  "$parent_root/human64.json" \
  reports/fresh_f3_hazard_mixed_league_seed1068701/training_stability.json; do
  [[ -f "$required" ]] || { print -u2 -- "missing mixed-league gate input: $required"; exit 1; }
done
[[ ! -e "$root/decision.json" ]] || { print -u2 -- "refusing existing league decision"; exit 1; }
mkdir -p "$root/candidate"

env PYTHONPATH=src:. uv run python run_clasher.py strategy-benchmark -- \
  --checkpoint "$candidate" --decks-path decks.json --sampling-decks-path "$development" \
  --games-per-opponent 6 --seed 1068601 --decision-interval 8 --max-ticks 6000 \
  --device cpu --reward-profile objective-v1 --quiet-engine \
  --json-out "$root/candidate/strategy.json" --markdown-out "$root/candidate/strategy.md" \
  > "$root/candidate/strategy.log" 2>&1
env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
  --checkpoint "$candidate" --opponent random --decks-path decks.json \
  --sampling-decks-path "$development" --games 24 --mirror-match --seed 1068602 \
  --decision-interval 8 --max-ticks 6000 --device cpu --reward-profile objective-v1 \
  --quiet-engine --json-out "$root/candidate/random24.metrics.json" \
  --games-json-out "$root/candidate/random24.games.json" > "$root/candidate/random24.log" 2>&1
env PYTHONPATH=src:. uv run python scripts/evaluate_recurrent_corpus.py \
  --corpus "$corpus" --public-observation-sidecar "$sidecar" \
  --checkpoint "$candidate" --decks-path decks.json --max-episodes 64 \
  --episode-seed 1068604 --device mps --json-out "$root/candidate/human64.json" \
  > "$root/candidate/human64.log" 2>&1
env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
  --checkpoint "$candidate" --opponent policy --opponent-checkpoint "$parent" \
  --decks-path decks.json --sampling-decks-path "$validation" --games 24 --mirror-match \
  --seed 1068803 --decision-interval 8 --max-ticks 6000 --device cpu \
  --reward-profile objective-v1 --quiet-engine --json-out "$root/candidate/direct24.metrics.json" \
  --games-json-out "$root/candidate/direct24.games.json" > "$root/candidate/direct24.log" 2>&1
env PYTHONPATH=src:. uv run python scripts/audit_policy_hand_slot_robustness.py \
  --checkpoint "$candidate" --decks-path decks.json --sampling-decks-path "$validation" \
  --designated-card card_action:HogRider --opponent-strategy balanced --games 2 \
  --seed 1068805 --decision-interval 8 --max-ticks 6000 --reward-profile objective-v1 \
  --general-stride 16 --max-general-decisions 512 \
  --json-out "$root/candidate/hand_robustness.json" \
  > "$root/candidate/hand_robustness.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/finalize_fresh_f3_hazard_mixed_league.py \
  --parent-root "$parent_root" --candidate-root "$root/candidate" \
  --stability reports/fresh_f3_hazard_mixed_league_seed1068701/training_stability.json \
  --output "$root/decision.json" 2>&1 | tee "$root/finalize.log"
