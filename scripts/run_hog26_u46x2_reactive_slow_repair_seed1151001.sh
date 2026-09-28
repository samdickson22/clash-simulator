#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

collector_checkpoint=checkpoints/hog26_clean8_aligned_seed1095001/calibrated/policy_v2_update_000010_threshold_0p2000.pt
fit_parent=checkpoints/hog26_executed_strategy_hazard_seed1108001/policy_v2_update_000014.pt
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
x2_root=datasets/derived/hog26_equal_plus_u46x2_seed1145001
target_root=datasets/derived/hog26_reactive_slow_extra_seed1151001
mix_root=datasets/derived/hog26_u46x2_reactive_slow_seed1152001
checkpoint_root=checkpoints/hog26_u46x2_reactive_slow_spatial_seed1153001
report_root=reports/hog26_u46x2_reactive_slow_spatial_seed1153001
fit_device=${FIT_DEVICE:-mps}
strategies=(reactive-defense slow-push)

for required in \
  "$collector_checkpoint" \
  "$fit_parent" \
  "$learner_decks" \
  "$opponent_decks" \
  "$x2_root/train/corpus.npz" \
  "$x2_root/train/public_v2.npz" \
  "$x2_root/validation/corpus.npz" \
  "$x2_root/validation/public_v2.npz"; do
  [[ -f "$required" ]] || { print -u2 -- "missing repair input: $required"; exit 1; }
done
[[ ! -e "$mix_root/COMPLETE" ]] || { print -u2 -- "refusing completed repair corpus"; exit 1; }
[[ ! -e "$checkpoint_root/candidate.pt" ]] || { print -u2 -- "refusing existing repair checkpoint"; exit 1; }

collect_shard() {
  local split=$1 strategy=$2 games=$3 seed=$4
  local shard_root="$target_root/$split/$strategy"
  mkdir -p "$shard_root"
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/collect_policy_context_corpus.py \
    --checkpoint "$collector_checkpoint" --decks-path decks.json \
    --learner-decks-path "$learner_decks" \
    --opponent-decks-path "$opponent_decks" \
    --games "$games" --seed "$seed" --teacher-strategy "$strategy" \
    --corpus-out "$shard_root/corpus.npz" \
    --sidecar-out "$shard_root/public_v2.npz" \
    --manifest-out "$shard_root/manifest.json" \
    > "$shard_root/collect.log" 2>&1
}

mkdir -p "$target_root" "$mix_root" "$checkpoint_root" "$report_root"
pids=()
for index in {1..2}; do
  strategy=${strategies[$index]}
  collect_shard train "$strategy" 24 $((1151001 + index * 100000)) &
  pids+=($!)
  collect_shard validation "$strategy" 8 $((1158001 + index * 100000)) &
  pids+=($!)
done
for pid in $pids; do
  wait "$pid"
done

for split in train validation; do
  mkdir -p "$mix_root/$split"
  env PYTHONPATH=src:. uv run python scripts/combine_causal_rehearsal_corpora.py \
    --corpus "$target_root/$split/reactive-defense/corpus.npz" \
    --sidecar "$target_root/$split/reactive-defense/public_v2.npz" \
    --corpus "$target_root/$split/slow-push/corpus.npz" \
    --sidecar "$target_root/$split/slow-push/public_v2.npz" \
    --corpus-out "$target_root/$split/corpus.npz" \
    --sidecar-out "$target_root/$split/public_v2.npz" \
    --manifest-out "$target_root/$split/manifest.json" \
    > "$target_root/$split/combine.log" 2>&1

  env PYTHONPATH=src:. uv run python scripts/combine_causal_rehearsal_corpora.py \
    --corpus "$x2_root/$split/corpus.npz" \
    --sidecar "$x2_root/$split/public_v2.npz" \
    --corpus "$target_root/$split/corpus.npz" \
    --sidecar "$target_root/$split/public_v2.npz" \
    --corpus-out "$mix_root/$split/corpus.npz" \
    --sidecar-out "$mix_root/$split/public_v2.npz" \
    --manifest-out "$mix_root/$split/manifest.json" \
    > "$mix_root/$split/combine.log" 2>&1
done
print -r -- 'hog26_u46x2_reactive_slow_seed1152001_complete_v1' > "$mix_root/COMPLETE"

env PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python -m clasher.rl.imitation fit \
  --corpus "$mix_root/train/corpus.npz" \
  --public-observation-sidecar "$mix_root/train/public_v2.npz" \
  --initial-checkpoint "$fit_parent" --decks-path decks.json \
  --output-checkpoint "$checkpoint_root/candidate.pt" \
  --control-checkpoint "$checkpoint_root/control.pt" \
  --manifest-out "$report_root/fit.json" \
  --seed 1153001 --split-seed 1153002 --epochs 3 --batch-size 32 \
  --learning-rate 2.5e-4 --validation-fraction 0.2 --device "$fit_device" \
  --sequence-length 64 --left-right-augmentation \
  --hand-permutation-augmentation \
  --hand-permutation-augmentation-probability 0.5 \
  --trim-entity-padding --placement-actions-only \
  --imitation-objective spatial-v1 --type-loss-coef 1.0 \
  --location-loss-coef 0.25 --anchor-policy-kl-coef 1.0 \
  --expert-card-balance-power 0.5 --max-expert-card-weight 3.0 \
  --max-combined-sample-weight 4.0 --defensive-context-weight 1.0 \
  --defensive-context-maximum-y 0.25 \
  --trainable-prefix semantic_slot_choice_query. \
  --trainable-prefix mechanics_slot_choice_query. \
  --trainable-prefix tile_projection. \
  --trainable-prefix memory_tile_film. \
  --trainable-prefix tile_decoder. \
  --trainable-prefix tile_key. \
  --trainable-prefix card_query. \
  --trainable-prefix location_bias. \
  > "$report_root/fit.log" 2>&1
