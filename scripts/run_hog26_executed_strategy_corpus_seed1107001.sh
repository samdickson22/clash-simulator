#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

checkpoint=checkpoints/hog26_clean8_aligned_seed1095001/calibrated/policy_v2_update_000010_threshold_0p2000.pt
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
balanced_config=configs/hog26_balanced_teacher_candidate17_seed1075201.json
root=datasets/derived/hog26_executed_strategy_seed1107001
strategies=(bridge-pressure slow-push spell-control reactive-defense split-lane balanced)

for required in "$checkpoint" "$learner_decks" "$opponent_decks" "$balanced_config"; do
  [[ -f "$required" ]] || { print -u2 -- "missing strategy-corpus input: $required"; exit 1; }
done
[[ ! -e "$root/COMPLETE" ]] || { print -u2 -- "refusing completed strategy corpus"; exit 1; }
mkdir -p "$root"

collect_shard() {
  local split=$1 strategy=$2 games=$3 seed=$4
  local shard_root="$root/$split/$strategy"
  local -a teacher_args
  mkdir -p "$shard_root"
  teacher_args=(--teacher-strategy "$strategy")
  if [[ "$strategy" == balanced ]]; then
    teacher_args+=(--teacher-balanced-config "$balanced_config")
  fi
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/collect_policy_context_corpus.py \
    --checkpoint "$checkpoint" --decks-path decks.json \
    --learner-decks-path "$learner_decks" \
    --opponent-decks-path "$opponent_decks" --games "$games" --seed "$seed" \
    ${teacher_args[@]} --corpus-out "$shard_root/corpus.npz" \
    --sidecar-out "$shard_root/public_v2.npz" \
    --manifest-out "$shard_root/manifest.json" \
    > "$shard_root/collect.log" 2>&1
}

pids=()
for index in {1..6}; do
  strategy=${strategies[$index]}
  collect_shard train "$strategy" 24 $((1107001 + index * 100000)) &
  pids+=($!)
  collect_shard validation "$strategy" 8 $((1114001 + index * 100000)) &
  pids+=($!)
done
for pid in $pids; do
  wait "$pid"
done

for split in train validation; do
  combine_args=()
  for strategy in $strategies; do
    combine_args+=(--corpus "$root/$split/$strategy/corpus.npz")
    combine_args+=(--sidecar "$root/$split/$strategy/public_v2.npz")
  done
  env PYTHONPATH=src:. uv run python scripts/combine_causal_rehearsal_corpora.py \
    ${combine_args[@]} --corpus-out "$root/$split/corpus.npz" \
    --sidecar-out "$root/$split/public_v2.npz" \
    --manifest-out "$root/$split/manifest.json" \
    > "$root/$split/combine.log" 2>&1
done

print -r -- 'hog26_executed_strategy_corpus_seed1107001_complete_v1' \
  > "$root/COMPLETE"
