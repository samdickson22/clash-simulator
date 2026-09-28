#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/hog26_clean8_aligned_seed1095001/calibrated/policy_v2_update_000010_threshold_0p2000.pt
corpus_root=datasets/derived/hog26_executed_strategy_seed1107001
checkpoint_root=checkpoints/hog26_executed_strategy_hazard_seed1108001
report_root=reports/hog26_executed_strategy_hazard_seed1108001
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json

for required in "$parent" "$corpus_root/COMPLETE" \
  "$corpus_root/train/corpus.npz" "$corpus_root/train/public_v2.npz"; do
  [[ -f "$required" ]] || { print -u2 -- "missing strategy-hazard input: $required"; exit 1; }
done
[[ ! -e "$checkpoint_root/policy_v2_update_000015.pt" ]] || {
  print -u2 -- "refusing existing strategy-hazard endpoint"
  exit 1
}
mkdir -p "$checkpoint_root" "$report_root"

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python run_clasher.py train -- \
  --decks-path decks.json --sampling-decks-path "$opponent_decks" \
  --learner-sampling-decks-path "$learner_decks" \
  --opponent-sampling-decks-path "$opponent_decks" \
  --checkpoint-dir "$checkpoint_root" --resume-from "$parent" \
  --seed 1108001 --updates 15 --num-envs 64 --actor-workers 12 --actor-threads 1 \
  --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
  --opponent-mode league --engine-fast-path on --device mps --actor-device cpu \
  --league-opponent random --league-opponent "$parent" \
  --pfsp-report reports/hog26_card_rehearsal_repair_gate_seed1070901/u46_full/strategy.json \
  --pfsp-strategy-workers 10 --hazard-conditioned-rollouts --reset-optimizer \
  --trainable-prefix play_hazard_head. --learning-rate 0.0001 \
  --gamma 0.995 --gae-lambda 0.95 --clip-ratio 0.2 --value-coef 0.5 \
  --entropy-coef 0 --action-type-entropy-coef 0 --location-entropy-coef 0 \
  --conditional-slot-entropy-coef 0 --hand-aux-coef 0 --elixir-aux-coef 0 \
  --epochs 1 --sequence-batch-size 4 --target-kl 0.05 \
  --causal-rehearsal-corpus "$corpus_root/train/corpus.npz" \
  --causal-rehearsal-public-sidecar "$corpus_root/train/public_v2.npz" \
  --causal-rehearsal-sequence-length 64 --causal-rehearsal-coef 10 \
  --causal-rehearsal-decision-coef 1 \
  --causal-rehearsal-decision-positive-weight 1 \
  --causal-rehearsal-card-coef 0 --causal-rehearsal-tile-coef 0 \
  --causal-rehearsal-batch-sequences 16 \
  --save-every 1 --log-every 1 --no-lr-anneal --quiet-engine \
  > "$report_root/train.log" 2>&1

for update in 10 11 12 13 14 15; do
  checkpoint="$parent"
  if (( update > 10 )); then
    checkpoint="$checkpoint_root/policy_v2_update_$(printf '%06d' "$update").pt"
  fi
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/evaluate_recurrent_corpus.py \
    --corpus "$corpus_root/validation/corpus.npz" \
    --public-observation-sidecar "$corpus_root/validation/public_v2.npz" \
    --checkpoint "$checkpoint" --decks-path decks.json --device cpu \
    --json-out "$report_root/validation_u${update}.json" \
    > "$report_root/validation_u${update}.stdout.json" 2>&1
done

print -r -- 'hog26_executed_strategy_hazard_seed1108001_complete_v1' \
  > "$report_root/COMPLETE"
