#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

policy=checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
output_root=datasets/derived/hog26_u46_terminal_cf_pilot_seed1085001

for required in "$policy" "$learner_decks" "$opponent_decks"; do
  [[ -f "$required" ]] || { print -u2 -- "missing counterfactual input: $required"; exit 1; }
done
[[ ! -e "$output_root/COMPLETE" ]] || { print -u2 -- "refusing completed pilot"; exit 1; }
mkdir -p "$output_root/train/shards" "$output_root/validation/shards"

collect_shard() {
  local split=$1 seed=$2 game=$3
  local padded root
  padded=$(printf '%03d' "$game")
  root="$output_root/$split/shards/shard_$padded"
  [[ ! -e "$root.npz" && ! -e "$root.json" ]] || {
    print -u2 -- "refusing existing shard: $root"
    return 1
  }
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/collect_terminal_counterfactual_corpus.py \
    --policy "$policy" --decks-path decks.json \
    --learner-sampling-decks-path "$learner_decks" \
    --opponent-sampling-decks-path "$opponent_decks" \
    --games 1 --game-offset "$game" --seed "$seed" --states-per-game 2 \
    --minimum-tick 256 --query-stride 64 --decision-interval 8 --max-ticks 6000 \
    --max-candidates 10 --locations-per-slot 2 --spatially-diverse-locations \
    --device cpu --torch-threads 1 --output "$root.npz" --report "$root.json" \
    > "$root.log" 2>&1
}

collect_split() {
  local split=$1 seed=$2 batch_start game pid
  local -a pids
  for batch_start in 0 6; do
    pids=()
    for (( game = batch_start; game < batch_start + 6; game++ )); do
      collect_shard "$split" "$seed" "$game" &
      pids+=($!)
    done
    for pid in $pids; do
      wait "$pid"
    done
  done
  env PYTHONPATH=src:. uv run python scripts/combine_terminal_counterfactual_corpora.py \
    --input-root "$output_root/$split/shards" --output "$output_root/$split.npz" \
    --report "$output_root/$split.json" > "$output_root/$split.combine.log" 2>&1
}

collect_split train 1085001
collect_split validation 1087001
print -r -- 'hog26_u46_terminal_cf_pilot_seed1085001_complete_v1' \
  > "$output_root/COMPLETE"
