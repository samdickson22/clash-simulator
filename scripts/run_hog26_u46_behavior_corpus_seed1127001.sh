#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

checkpoint=checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
experiment_seed=${EXPERIMENT_SEED:-1127001}
validation_seed=$((experiment_seed + 700000))
root=datasets/derived/hog26_u46_behavior_seed${experiment_seed}

for required in "$checkpoint" "$learner_decks" "$opponent_decks"; do
  [[ -f "$required" ]] || { print -u2 -- "missing u46 corpus input: $required"; exit 1; }
done
[[ ! -e "$root/COMPLETE" ]] || { print -u2 -- "refusing completed u46 corpus"; exit 1; }
mkdir -p "$root"

collect_shard() {
  local split=$1 shard=$2 games=$3 seed=$4
  local shard_root="$root/$split/shard_$shard"
  mkdir -p "$shard_root"
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/collect_policy_context_corpus.py \
    --checkpoint "$checkpoint" --decks-path decks.json \
    --learner-decks-path "$learner_decks" --opponent-decks-path "$opponent_decks" \
    --games "$games" --seed "$seed" --corpus-out "$shard_root/corpus.npz" \
    --sidecar-out "$shard_root/public_v2.npz" \
    --manifest-out "$shard_root/manifest.json" > "$shard_root/collect.log" 2>&1
}

pids=()
for shard in {0..5}; do
  collect_shard train "$shard" 12 $((experiment_seed + shard * 100000)) &
  pids+=($!)
done
for shard in {0..2}; do
  collect_shard validation "$shard" 8 $((validation_seed + shard * 100000)) &
  pids+=($!)
done
for pid in $pids; do wait "$pid"; done

for split in train validation; do
  combine_args=()
  for shard_root in "$root/$split"/shard_*; do
    combine_args+=(--corpus "$shard_root/corpus.npz")
    combine_args+=(--sidecar "$shard_root/public_v2.npz")
  done
  env PYTHONPATH=src:. uv run python scripts/combine_causal_rehearsal_corpora.py \
    ${combine_args[@]} --corpus-out "$root/$split/corpus.npz" \
    --sidecar-out "$root/$split/public_v2.npz" \
    --manifest-out "$root/$split/manifest.json" > "$root/$split/combine.log" 2>&1
done

print -r -- "hog26_u46_behavior_corpus_seed${experiment_seed}_complete_v1" \
  > "$root/COMPLETE"
