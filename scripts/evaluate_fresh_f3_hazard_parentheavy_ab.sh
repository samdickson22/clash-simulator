#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/fresh_f3_hazard_parentheavy_ab_gate_seed1070001
anchor=checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000023.pt
parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
plain=checkpoints/fresh_f3_hazard_parentheavy_ab_seed1069901/plain/policy_v2_update_000028.pt
kl005=checkpoints/fresh_f3_hazard_parentheavy_ab_seed1069901/kl005/policy_v2_update_000028.pt
decks=datasets/deck_curriculum_v3_seed1056101/pfsp_tuning_strict_v2_holdouts.json
validation=datasets/deck_curriculum_v3_seed1056101/validation.json
hog=training_decks/katacr_hog26_only.json
corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz

for required in "$anchor" "$parent" "$plain" "$kl005" "$decks" "$validation" \
  "$hog" "$corpus" "$sidecar" reports/fresh_f3_hazard_parentheavy_ab_seed1069901/COMPLETE; do
  [[ -f "$required" ]] || { print -u2 -- "missing parent-heavy gate input: $required"; exit 1; }
done
[[ ! -e "$root/COMPLETE" ]] || { print -u2 -- "refusing completed gate"; exit 1; }
mkdir -p "$root"

evaluate_arm() {
  local arm=$1
  local checkpoint=$2
  mkdir -p "$root/$arm"
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py eval -- \
    --checkpoint "$checkpoint" --opponent policy --opponent-checkpoint "$parent" \
    --sampling-decks-path "$validation" --games 24 --mirror-match --seed 1070001 \
    --decision-interval 8 --max-ticks 6000 --device cpu --reward-profile objective-v1 \
    --quiet-engine --json-out "$root/$arm/direct24.metrics.json" \
    --games-json-out "$root/$arm/direct24.games.json" > "$root/$arm/direct24.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py strategy-benchmark -- \
    --checkpoint "$checkpoint" --sampling-decks-path "$decks" \
    --games-per-opponent 4 --seed 1070002 --decision-interval 8 --max-ticks 6000 \
    --device cpu --reward-profile objective-v1 --quiet-engine \
    --json-out "$root/$arm/strategy.json" --markdown-out "$root/$arm/strategy.md" \
    > "$root/$arm/strategy.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py eval -- \
    --checkpoint "$checkpoint" --opponent random --sampling-decks-path "$decks" \
    --games 24 --mirror-match --seed 1070003 --decision-interval 8 --max-ticks 6000 \
    --device cpu --reward-profile objective-v1 --quiet-engine \
    --json-out "$root/$arm/random24.metrics.json" \
    --games-json-out "$root/$arm/random24.games.json" > "$root/$arm/random24.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py eval -- \
    --checkpoint "$checkpoint" --opponent strategy --opponent-strategy balanced \
    --sampling-decks-path "$hog" --games 12 --mirror-match --seed 1070004 \
    --decision-interval 8 --max-ticks 6000 --device cpu --reward-profile objective-v1 \
    --quiet-engine --json-out "$root/$arm/hog12.metrics.json" \
    --games-json-out "$root/$arm/hog12.games.json" > "$root/$arm/hog12.log" 2>&1
}

typeset -a pids
pids=()
evaluate_arm anchor "$anchor" & pids+=($!)
evaluate_arm plain "$plain" & pids+=($!)
evaluate_arm kl005 "$kl005" & pids+=($!)
failed=0
for pid in $pids; do
  wait "$pid" || failed=1
done
(( failed == 0 )) || exit 1

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python \
  scripts/evaluate_recurrent_corpus.py --corpus "$corpus" \
  --public-observation-sidecar "$sidecar" --checkpoint "$anchor" \
  --checkpoint "$plain" --checkpoint "$kl005" --decks-path decks.json \
  --max-episodes 64 --episode-seed 1070005 --device cpu \
  --json-out "$root/human64.json" > "$root/human64.log" 2>&1
print -r -- 'fresh_f3_hazard_parentheavy_ab_gate_complete_v1' > "$root/COMPLETE"
