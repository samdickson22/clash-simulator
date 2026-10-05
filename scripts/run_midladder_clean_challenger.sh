#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt
challenger_seed=${CHALLENGER_SEED:-1048701}
learning_rate=${CHALLENGER_LR:-1e-5}
end_update=${CHALLENGER_END_UPDATE:-104}
challenger_tag=${CHALLENGER_TAG:-midladder_clean_history4_league_seed1048701}
checkpoint_dir=checkpoints/$challenger_tag
train_pool=datasets/deck_curriculum_v2_seed1040001/train_without_tv_raw2000_human_meta.json

for required in \
  "$parent" \
  "$train_pool" \
  checkpoints/generalized_twentyfourth_robust2_kernel999_lr01_seed15033/policy_v2_repair_step_0050.pt \
  checkpoints/katacr_human_u28_repair3_fresh60701_stage2_seed60702/policy_v2_repair_step_0200.pt \
  checkpoints/human_safety_student6m_u64_safetyrescue_seed1014001/policy_v2_update_000080.pt \
  checkpoints/human_safety_student6m_u80_cleananchor_rescue_seed1015001/policy_v2_update_000112.pt
do
  if [[ ! -f "$required" ]]; then
    print -u2 -r -- "missing clean-challenger input: $required"
    exit 1
  fi
done

for update in $(seq 41 "$end_update"); do
  checkpoint="$checkpoint_dir/policy_v2_update_$(printf '%06d' "$update").pt"
  if [[ -e "$checkpoint" ]]; then
    print -u2 -r -- "refusing stale challenger checkpoint: $checkpoint"
    exit 1
  fi
done

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py train -- \
  --decks-path decks.json \
  --sampling-decks-path "$train_pool" \
  --checkpoint-dir "$checkpoint_dir" \
  --resume-from "$parent" \
  --add-public-history-slots 4 \
  --seed "$challenger_seed" \
  --updates "$end_update" \
  --num-envs 64 \
  --actor-workers 12 \
  --actor-threads 1 \
  --trim-rollout-entity-padding \
  --rollout-steps 64 \
  --decision-interval 8 \
  --max-ticks 6000 \
  --reward-profile defense-v2 \
  --opponent-mode league \
  --league-opponent random \
  --league-opponent strategy:reactive-defense \
  --league-opponent strategy:reactive-defense \
  --league-opponent strategy:slow-push \
  --league-opponent strategy:slow-push \
  --league-opponent strategy:balanced \
  --league-opponent "$parent" \
  --league-opponent "$parent" \
  --league-opponent checkpoints/generalized_twentyfourth_robust2_kernel999_lr01_seed15033/policy_v2_repair_step_0050.pt \
  --league-opponent checkpoints/katacr_human_u28_repair3_fresh60701_stage2_seed60702/policy_v2_repair_step_0200.pt \
  --league-opponent checkpoints/human_safety_student6m_u64_safetyrescue_seed1014001/policy_v2_update_000080.pt \
  --league-opponent checkpoints/human_safety_student6m_u80_cleananchor_rescue_seed1015001/policy_v2_update_000112.pt \
  --engine-fast-path on \
  --device mps \
  --actor-device cpu \
  --trainable-prefix actor_encoder. \
  --trainable-prefix memory. \
  --trainable-prefix public_history_ \
  --trainable-prefix action_type_embedding. \
  --trainable-prefix action_type_head. \
  --trainable-prefix tile_projection. \
  --trainable-prefix memory_tile_film. \
  --trainable-prefix tile_decoder. \
  --trainable-prefix tile_key. \
  --trainable-prefix card_query. \
  --trainable-prefix location_bias. \
  --trainable-prefix critic_encoder. \
  --trainable-prefix value_head. \
  --learning-rate "$learning_rate" \
  --reset-optimizer \
  --gamma 0.995 \
  --gae-lambda 0.95 \
  --clip-ratio 0.2 \
  --value-coef 0.5 \
  --entropy-coef 0.01 \
  --anchor-checkpoint "$parent" \
  --anchor-l2-coef 0 \
  --anchor-policy-kl-coef 0.02 \
  --hand-aux-coef 0 \
  --elixir-aux-coef 0 \
  --epochs 2 \
  --sequence-batch-size 2 \
  --target-kl 0.03 \
  --save-every 1 \
  --log-every 1 \
  --no-lr-anneal \
  --quiet-engine \
  2>&1 | tee "reports/${challenger_tag}.log"
