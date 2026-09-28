#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/hog26_hazard_conditioned_spatial_rl_seed1083001/policy_v2_update_000056.pt
anchor=checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt
checkpoint_root=checkpoints/hog26_hazard_conditioned_spatial_rl_seed1083001
report_root=reports/hog26_hazard_conditioned_spatial_rl_seed1083001
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
pfsp=reports/hog26_card_rehearsal_repair_gate_seed1070901/u46_full/strategy.json
endpoint="$checkpoint_root/policy_v2_update_000076.pt"

for required in "$parent" "$anchor" "$learner_decks" "$opponent_decks" "$pfsp"; do
  [[ -f "$required" ]] || { print -u2 -- "missing conditioned continuation input: $required"; exit 1; }
done
[[ ! -e "$endpoint" ]] || { print -u2 -- "refusing existing conditioned endpoint"; exit 1; }

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python run_clasher.py train -- \
  --decks-path decks.json --sampling-decks-path "$opponent_decks" \
  --learner-sampling-decks-path "$learner_decks" \
  --opponent-sampling-decks-path "$opponent_decks" \
  --checkpoint-dir "$checkpoint_root" --resume-from "$parent" \
  --seed 1083001 --updates 76 --num-envs 64 --actor-workers 12 --actor-threads 1 \
  --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
  --opponent-mode league --engine-fast-path on --device mps --actor-device cpu \
  --league-opponent random --league-opponent "$anchor" \
  --pfsp-report "$pfsp" --pfsp-strategy-workers 10 \
  --hazard-conditioned-rollouts --reset-optimizer \
  --trainable-prefix semantic_slot_choice_query. \
  --trainable-prefix mechanics_slot_choice_query. \
  --trainable-prefix tile_projection. \
  --trainable-prefix memory_tile_film. \
  --trainable-prefix tile_decoder. \
  --trainable-prefix tile_key. \
  --trainable-prefix card_query. \
  --trainable-prefix location_bias. \
  --learning-rate 0.00003 --gamma 0.995 --gae-lambda 0.95 \
  --clip-ratio 0.2 --value-coef 0.5 --entropy-coef 0.0 \
  --action-type-entropy-coef 0.0 --location-entropy-coef 0.005 \
  --conditional-slot-entropy-coef 0.005 --hand-aux-coef 0 --elixir-aux-coef 0 \
  --epochs 2 --sequence-batch-size 4 --target-kl 0.05 \
  --save-every 1 --log-every 1 --no-lr-anneal --quiet-engine \
  > "$report_root/train_to76.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$parent" --checkpoint-dir "$checkpoint_root" \
  --start-update 57 --end-update 76 --max-approx-kl 0.05 \
  --max-anchor-policy-kl 0.05 --max-clip-fraction 0.30 \
  --output "$report_root/training_stability_to76.json"
print -r -- 'hog26_hazard_conditioned_spatial_rl_seed1083001_to76_complete_v1' \
  > "$report_root/COMPLETE_TO76"
