#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/hog26_executed_strategy_spatial_seed1109001/candidate.pt
champion=checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt
corpus_root=datasets/derived/hog26_executed_strategy_seed1107001
checkpoint_root=checkpoints/hog26_u46_spatial_league_seed1111001
report_root=reports/hog26_u46_spatial_league_seed1111001
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json

for required in "$parent" "$champion" "$corpus_root/COMPLETE"; do
  [[ -f "$required" ]] || { print -u2 -- "missing spatial-league input: $required"; exit 1; }
done
[[ ! -e "$checkpoint_root/policy_v2_update_000019.pt" ]] || {
  print -u2 -- "refusing existing spatial-league endpoint"
  exit 1
}
mkdir -p "$checkpoint_root" "$report_root"

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python scripts/run_clasher.py train -- \
  --decks-path decks.json --sampling-decks-path "$opponent_decks" \
  --learner-sampling-decks-path "$learner_decks" \
  --opponent-sampling-decks-path "$opponent_decks" \
  --checkpoint-dir "$checkpoint_root" --resume-from "$parent" \
  --seed 1111001 --updates 19 --num-envs 64 --actor-workers 12 --actor-threads 1 \
  --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
  --opponent-mode league --engine-fast-path on --device mps --actor-device cpu \
  --league-opponent random --league-opponent "$parent" \
  --league-opponent "$champion" \
  --pfsp-report reports/hog26_card_rehearsal_repair_gate_seed1070901/u46_full/strategy.json \
  --pfsp-strategy-workers 9 --hazard-conditioned-rollouts --reset-optimizer \
  --anchor-checkpoint "$parent" --anchor-l2-coef 0.0001 \
  --anchor-policy-kl-coef 0.10 \
  --trainable-prefix semantic_slot_choice_query. \
  --trainable-prefix mechanics_slot_choice_query. \
  --trainable-prefix tile_projection. --trainable-prefix memory_tile_film. \
  --trainable-prefix tile_decoder. --trainable-prefix tile_key. \
  --trainable-prefix card_query. --trainable-prefix location_bias. \
  --learning-rate 0.00001 --gamma 0.995 --gae-lambda 0.95 --clip-ratio 0.2 \
  --value-coef 0.5 --entropy-coef 0.005 --action-type-entropy-coef 0 \
  --location-entropy-coef 0.005 --conditional-slot-entropy-coef 0.005 \
  --hand-aux-coef 0 --elixir-aux-coef 0 --epochs 1 --sequence-batch-size 4 \
  --target-kl 0.03 --no-lr-anneal \
  --causal-rehearsal-corpus "$corpus_root/train/corpus.npz" \
  --causal-rehearsal-public-sidecar "$corpus_root/train/public_v2.npz" \
  --causal-rehearsal-sequence-length 64 --causal-rehearsal-coef 2 \
  --causal-rehearsal-decision-coef 0 \
  --causal-rehearsal-card-coef 1 --causal-rehearsal-tile-coef 0.25 \
  --causal-rehearsal-batch-sequences 4 \
  --save-every 1 --log-every 1 --quiet-engine \
  > "$report_root/train.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$parent" --checkpoint-dir "$checkpoint_root" \
  --start-update 15 --end-update 19 --max-approx-kl 0.03 \
  --max-anchor-policy-kl 0.03 --max-clip-fraction 0.30 \
  --output "$report_root/training_stability.json"

print -r -- 'hog26_u46_spatial_league_seed1111001_complete_v1' \
  > "$report_root/COMPLETE"
