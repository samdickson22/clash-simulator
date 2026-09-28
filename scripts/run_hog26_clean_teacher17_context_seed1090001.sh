#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

checkpoint=checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
teacher_config=configs/hog26_balanced_teacher_candidate17_seed1075201.json
experiment_seed=${EXPERIMENT_SEED:-1090001}
root=datasets/derived/hog26_clean_teacher17_context_seed${experiment_seed}

for required in "$checkpoint" "$learner_decks" "$opponent_decks" "$teacher_config"; do
  [[ -f "$required" ]] || { print -u2 -- "missing clean-context input: $required"; exit 1; }
done
[[ ! -e "$root/COMPLETE" ]] || { print -u2 -- "refusing completed clean context"; exit 1; }
mkdir -p "$root"

pids=()
for shard in 0 1 2 3; do
  shard_root="$root/shard_$shard"
  mkdir -p "$shard_root"
  seed=$((experiment_seed + shard * 100000))
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 uv run python \
    scripts/collect_policy_context_corpus.py \
    --checkpoint "$checkpoint" --decks-path decks.json \
    --learner-decks-path "$learner_decks" \
    --opponent-decks-path "$opponent_decks" --games 6 --seed "$seed" \
    --teacher-strategy balanced --teacher-balanced-config "$teacher_config" \
    --execute-policy-behavior --corpus-out "$shard_root/corpus.npz" \
    --sidecar-out "$shard_root/public_v2.npz" \
    --manifest-out "$shard_root/manifest.json" \
    > "$shard_root/collect.log" 2>&1 &
  pids+=($!)
done
for pid in $pids; do
  wait "$pid"
done

combine_args=()
for shard in 0 1 2 3; do
  combine_args+=(--corpus "$root/shard_$shard/corpus.npz")
  combine_args+=(--sidecar "$root/shard_$shard/public_v2.npz")
done
env PYTHONPATH=src:. uv run python scripts/combine_causal_rehearsal_corpora.py \
  $combine_args --corpus-out "$root/corpus.npz" \
  --sidecar-out "$root/public_v2.npz" --manifest-out "$root/manifest.json" \
  > "$root/combine.log" 2>&1
print -r -- "hog26_clean_teacher17_context_seed${experiment_seed}_complete_v1" \
  > "$root/COMPLETE"
