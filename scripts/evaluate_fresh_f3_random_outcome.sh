#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/fresh_f3_random_outcome_seed1067701
parent=checkpoints/fresh_f3_outcome_lineage_seed1067501/control.pt
candidate=checkpoints/fresh_f3_random_outcome_seed1067701/policy_v2_update_000020.pt
development=datasets/deck_curriculum_v3_seed1056101/pfsp_tuning_strict_v2_holdouts.json
validation=datasets/deck_curriculum_v3_seed1056101/validation.json
human=datasets/derived/tv_royale_youtube_causal_imitation_seed1067006/corpus.npz
human_sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067006/public_v2.npz

for required in "$root/training_stability.json" "$parent" "$candidate"; do
  [[ -f "$required" ]] || { print -u2 -- "missing F3 evaluation input: $required"; exit 1; }
done
[[ ! -e "$root/decision.json" ]] || { print -u2 -- "refusing existing F3 decision"; exit 1; }

for arm in parent candidate; do
  checkpoint=$parent
  [[ "$arm" == candidate ]] && checkpoint=$candidate
  mkdir -p "$root/$arm"
  env PYTHONPATH=src:. uv run python scripts/run_clasher.py strategy-benchmark -- \
    --checkpoint "$checkpoint" --decks-path decks.json --sampling-decks-path "$development" \
    --games-per-opponent 6 --seed 1067801 --decision-interval 8 --max-ticks 6000 \
    --device cpu --reward-profile objective-v1 --quiet-engine \
    --json-out "$root/$arm/strategy.json" --markdown-out "$root/$arm/strategy.md" \
    > "$root/$arm/strategy.log" 2>&1
  env PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$checkpoint" --opponent random --decks-path decks.json \
    --sampling-decks-path "$development" --games 24 --mirror-match --seed 1067802 \
    --decision-interval 8 --max-ticks 6000 --device cpu --reward-profile objective-v1 \
    --quiet-engine --json-out "$root/$arm/random24.metrics.json" \
    --games-json-out "$root/$arm/random24.games.json" > "$root/$arm/random24.log" 2>&1
  env PYTHONPATH=src:. uv run python scripts/evaluate_recurrent_corpus.py \
    --corpus "$human" --public-observation-sidecar "$human_sidecar" \
    --checkpoint "$checkpoint" --decks-path decks.json --max-episodes 64 \
    --episode-seed 1067804 --device mps --json-out "$root/$arm/human64.json" \
    > "$root/$arm/human64.log" 2>&1
done

env PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
  --checkpoint "$candidate" --opponent policy --opponent-checkpoint "$parent" \
  --decks-path decks.json --sampling-decks-path "$validation" --games 24 --mirror-match \
  --seed 1067803 --decision-interval 8 --max-ticks 6000 --device cpu \
  --reward-profile objective-v1 --quiet-engine --json-out "$root/candidate/direct24.metrics.json" \
  --games-json-out "$root/candidate/direct24.games.json" > "$root/candidate/direct24.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/audit_policy_hand_slot_robustness.py \
  --checkpoint "$candidate" --decks-path decks.json --sampling-decks-path "$validation" \
  --designated-card card_action:HogRider \
  --opponent-strategy balanced --games 2 --seed 1067805 --decision-interval 8 \
  --max-ticks 6000 --reward-profile objective-v1 --general-stride 16 \
  --max-general-decisions 512 --json-out "$root/candidate/hand_robustness.json" \
  > "$root/candidate/hand_robustness.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/finalize_fresh_f3_random_outcome.py \
  --root "$root" --output "$root/decision.json" 2>&1 | tee "$root/finalize.log"
