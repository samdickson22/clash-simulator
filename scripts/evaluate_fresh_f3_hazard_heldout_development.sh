#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/fresh_f3_hazard_heldout_development_seed1068901
parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
candidate=checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000030.pt
heldout=datasets/deck_curriculum_v3_seed1056101/heldout.json

for required in "$parent" "$candidate" "$heldout" \
  reports/fresh_f3_hazard_mixed_league_gate_seed1068801/decision.json; do
  [[ -f "$required" ]] || { print -u2 -- "missing heldout input: $required"; exit 1; }
done
[[ ! -e "$root/decision.json" ]] || { print -u2 -- "refusing existing heldout decision"; exit 1; }
mkdir -p "$root"

for arm in parent candidate; do
  checkpoint=$parent
  [[ "$arm" == candidate ]] && checkpoint=$candidate
  mkdir -p "$root/$arm"
  env PYTHONPATH=src:. uv run python run_clasher.py strategy-benchmark -- \
    --checkpoint "$checkpoint" --decks-path decks.json --sampling-decks-path "$heldout" \
    --games-per-opponent 4 --seed 1068901 --decision-interval 8 --max-ticks 6000 \
    --device cpu --reward-profile objective-v1 --quiet-engine \
    --json-out "$root/$arm/strategy.json" --markdown-out "$root/$arm/strategy.md" \
    > "$root/$arm/strategy.log" 2>&1
  env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$checkpoint" --opponent random --decks-path decks.json \
    --sampling-decks-path "$heldout" --games 24 --mirror-match --seed 1068902 \
    --decision-interval 8 --max-ticks 6000 --device cpu --reward-profile objective-v1 \
    --quiet-engine --json-out "$root/$arm/random24.metrics.json" \
    --games-json-out "$root/$arm/random24.games.json" > "$root/$arm/random24.log" 2>&1
done

env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
  --checkpoint "$candidate" --opponent policy --opponent-checkpoint "$parent" \
  --decks-path decks.json --sampling-decks-path "$heldout" --games 48 --mirror-match \
  --seed 1068903 --decision-interval 8 --max-ticks 6000 --device cpu \
  --reward-profile objective-v1 --quiet-engine --json-out "$root/candidate/direct48.metrics.json" \
  --games-json-out "$root/candidate/direct48.games.json" > "$root/candidate/direct48.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/finalize_fresh_f3_hazard_heldout.py \
  --root "$root" --output "$root/decision.json" 2>&1 | tee "$root/finalize.log"
