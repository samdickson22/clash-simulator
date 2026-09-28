#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/fresh_f3_hazard_fullweight_update20_seed1068601
parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000010.pt
candidate=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
development=datasets/deck_curriculum_v3_seed1056101/pfsp_tuning_strict_v2_holdouts.json
validation=datasets/deck_curriculum_v3_seed1056101/validation.json
corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz

for required in "$parent" "$candidate" "$corpus" "$sidecar" \
  reports/fresh_f3_hazard_fullweight_outcome_seed1068401/training_stability_11_20.json; do
  [[ -f "$required" ]] || { print -u2 -- "missing update-20 input: $required"; exit 1; }
done
[[ ! -e "$root/decision.json" ]] || { print -u2 -- "refusing existing decision"; exit 1; }
mkdir -p "$root"

for arm in parent candidate; do
  checkpoint=$parent
  [[ "$arm" == candidate ]] && checkpoint=$candidate
  mkdir -p "$root/$arm"
  env PYTHONPATH=src:. uv run python run_clasher.py strategy-benchmark -- \
    --checkpoint "$checkpoint" --decks-path decks.json --sampling-decks-path "$development" \
    --games-per-opponent 6 --seed 1068601 --decision-interval 8 --max-ticks 6000 \
    --device cpu --reward-profile objective-v1 --quiet-engine \
    --json-out "$root/$arm/strategy.json" --markdown-out "$root/$arm/strategy.md" \
    > "$root/$arm/strategy.log" 2>&1
  env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$checkpoint" --opponent random --decks-path decks.json \
    --sampling-decks-path "$development" --games 24 --mirror-match --seed 1068602 \
    --decision-interval 8 --max-ticks 6000 --device cpu --reward-profile objective-v1 \
    --quiet-engine --json-out "$root/$arm/random24.metrics.json" \
    --games-json-out "$root/$arm/random24.games.json" > "$root/$arm/random24.log" 2>&1
  env PYTHONPATH=src:. uv run python scripts/evaluate_recurrent_corpus.py \
    --corpus "$corpus" --public-observation-sidecar "$sidecar" \
    --checkpoint "$checkpoint" --decks-path decks.json --max-episodes 64 \
    --episode-seed 1068604 --device mps --json-out "$root/$arm/human64.json" \
    > "$root/$arm/human64.log" 2>&1
done

env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
  --checkpoint "$candidate" --opponent policy --opponent-checkpoint "$parent" \
  --decks-path decks.json --sampling-decks-path "$validation" --games 24 --mirror-match \
  --seed 1068603 --decision-interval 8 --max-ticks 6000 --device cpu \
  --reward-profile objective-v1 --quiet-engine --json-out "$root/candidate/direct24.metrics.json" \
  --games-json-out "$root/candidate/direct24.games.json" > "$root/candidate/direct24.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/audit_policy_hand_slot_robustness.py \
  --checkpoint "$candidate" --decks-path decks.json --sampling-decks-path "$validation" \
  --designated-card card_action:HogRider --opponent-strategy balanced --games 2 \
  --seed 1068605 --decision-interval 8 --max-ticks 6000 --reward-profile objective-v1 \
  --general-stride 16 --max-general-decisions 512 \
  --json-out "$root/candidate/hand_robustness.json" \
  > "$root/candidate/hand_robustness.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/finalize_fresh_f3_hazard_update20.py \
  --root "$root" --stability \
  reports/fresh_f3_hazard_fullweight_outcome_seed1068401/training_stability_11_20.json \
  --output "$root/decision.json" 2>&1 | tee "$root/finalize.log"
