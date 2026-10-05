#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/fresh_f3_hazard_expanded_safety_seed1069001
parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
candidate=checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000030.pt
heldout=datasets/deck_curriculum_v2_seed1040001/heldout.json
hog=training_decks/katacr_hog26_only.json
corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz

for required in "$parent" "$candidate" "$heldout" "$hog" "$corpus" "$sidecar" \
  reports/fresh_f3_hazard_heldout_development_seed1068901/decision.json; do
  [[ -f "$required" ]] || { print -u2 -- "missing expanded-safety input: $required"; exit 1; }
done
[[ $(jq -r '.expanded_safety_evaluation_authorized' \
  reports/fresh_f3_hazard_heldout_development_seed1068901/decision.json) == true ]] || {
  print -u2 -- "held-out gate did not authorize expanded safety evaluation"
  exit 1
}
[[ ! -e "$root/decision.json" ]] || { print -u2 -- "refusing existing decision"; exit 1; }
mkdir -p "$root"

typeset -a pids
pids=()

flush_jobs() {
  local failed=0
  local pid
  for pid in $pids; do
    wait "$pid" || failed=1
  done
  pids=()
  (( failed == 0 )) || return 1
}

queue_eval() {
  local role=$1
  local block=$2
  local name=$3
  local checkpoint=$4
  local games=$5
  local seed=$6
  shift 6
  local output_root="$root/block${block}"
  mkdir -p "$output_root"
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. \
    OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
    uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$checkpoint" "$@" --games "$games" --mirror-match \
    --seed "$seed" --decision-interval 8 --max-ticks 6000 --device cpu \
    --reward-profile objective-v1 --quiet-engine \
    --json-out "$output_root/${role}_${name}.metrics.json" \
    --games-json-out "$output_root/${role}_${name}.games.json" \
    > "$output_root/${role}_${name}.log" 2>&1 &
  pids+=($!)
  if (( ${#pids[@]} >= 4 )); then
    flush_jobs
  fi
}

queue_pair() {
  local block=$1
  local name=$2
  local games=$3
  local seed=$4
  shift 4
  queue_eval parent "$block" "$name" "$parent" "$games" "$seed" "$@"
  queue_eval candidate "$block" "$name" "$candidate" "$games" "$seed" "$@"
}

for block in 0 1 2; do
  seed_base=$((1069000 + block * 100))
  queue_pair "$block" random12 12 $((seed_base + 10)) \
    --opponent random --sampling-decks-path "$heldout"
  queue_pair "$block" balanced12 12 $((seed_base + 11)) \
    --opponent strategy --opponent-strategy balanced --sampling-decks-path "$heldout"
  queue_pair "$block" reactive12 12 $((seed_base + 12)) \
    --opponent strategy --opponent-strategy reactive-defense --sampling-decks-path "$heldout"
  queue_pair "$block" bridge6 6 $((seed_base + 13)) \
    --opponent strategy --opponent-strategy bridge-pressure --sampling-decks-path "$heldout"
  queue_pair "$block" slow6 6 $((seed_base + 14)) \
    --opponent strategy --opponent-strategy slow-push --sampling-decks-path "$heldout"
  queue_pair "$block" spell6 6 $((seed_base + 15)) \
    --opponent strategy --opponent-strategy spell-control --sampling-decks-path "$heldout"
  queue_pair "$block" split6 6 $((seed_base + 16)) \
    --opponent strategy --opponent-strategy split-lane --sampling-decks-path "$heldout"
  queue_pair "$block" hog12 12 $((seed_base + 17)) \
    --opponent strategy --opponent-strategy balanced --sampling-decks-path "$hog"
done
flush_jobs

for block in 0 1 2; do
  for name in random12 balanced12 reactive12 bridge6 slow6 spell6 split6 hog12; do
    env PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
      --baseline "$root/block${block}/parent_${name}.games.json" \
      --candidate "$root/block${block}/candidate_${name}.games.json" \
      --output "$root/block${block}/${name}.compare.json" > /dev/null
  done
done

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
  --checkpoint "$candidate" --opponent policy --opponent-checkpoint "$parent" \
  --sampling-decks-path "$heldout" --games 96 --mirror-match --seed 1069401 \
  --decision-interval 8 --max-ticks 6000 --device cpu --reward-profile objective-v1 \
  --quiet-engine --json-out "$root/direct96.metrics.json" \
  --games-json-out "$root/direct96.games.json" > "$root/direct96.log" 2>&1

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python \
  scripts/evaluate_recurrent_corpus.py \
  --corpus "$corpus" --public-observation-sidecar "$sidecar" \
  --checkpoint "$parent" --checkpoint "$candidate" --decks-path decks.json \
  --device mps --json-out "$root/human_all.json" > "$root/human_all.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/finalize_fresh_f3_hazard_expanded_safety.py \
  --root "$root" --parent "$parent" --candidate "$candidate" \
  --heldout-decks "$heldout" --hog-decks "$hog" \
  --human-corpus "$corpus" --human-sidecar "$sidecar" \
  --output "$root/decision.json" 2>&1 | tee "$root/finalize.log"
