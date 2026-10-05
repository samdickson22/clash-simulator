#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

resume=${BELIEF_RESUME:-checkpoints/public_cycle_belief_pretrain_seed1048803/policy_v2_update_000040_belief.pt}
anchor=checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt
pilot_seed=${BELIEF_PILOT_SEED:-1048901}
learning_rate=${BELIEF_PILOT_LR:-1e-5}
end_update=${BELIEF_PILOT_END_UPDATE:-48}
pilot_tag=${BELIEF_PILOT_TAG:-midladder_belief_projection_seed1048901}
checkpoint_dir=checkpoints/$pilot_tag
train_pool=datasets/deck_curriculum_v2_seed1040001/train_without_tv_raw2000_human_meta.json
belief_interface=${BELIEF_INTERFACE:-trunk}
if [[ "$belief_interface" == trunk ]]; then
  trainable_args=(--trainable-prefix public_history_projection.2.weight)
elif [[ "$belief_interface" == relational ]]; then
  trainable_args=(
    --trainable-prefix public_belief_card_query.weight
    --trainable-prefix public_belief_timing_head.weight
  )
else
  print -u2 -r -- "unknown belief interface: $belief_interface"
  exit 1
fi

for required in \
  "$resume" \
  "$anchor" \
  "$train_pool" \
  checkpoints/generalized_twentyfourth_robust2_kernel999_lr01_seed15033/policy_v2_repair_step_0050.pt \
  checkpoints/katacr_human_u28_repair3_fresh60701_stage2_seed60702/policy_v2_repair_step_0200.pt \
  checkpoints/human_safety_student6m_u64_safetyrescue_seed1014001/policy_v2_update_000080.pt \
  checkpoints/human_safety_student6m_u80_cleananchor_rescue_seed1015001/policy_v2_update_000112.pt
do
  if [[ ! -f "$required" ]]; then
    print -u2 -r -- "missing belief-pilot input: $required"
    exit 1
  fi
done

for update in $(seq 41 "$end_update"); do
  checkpoint="$checkpoint_dir/policy_v2_update_$(printf '%06d' "$update").pt"
  if [[ -e "$checkpoint" ]]; then
    print -u2 -r -- "refusing stale belief-pilot checkpoint: $checkpoint"
    exit 1
  fi
done

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py train -- \
  --decks-path decks.json \
  --sampling-decks-path "$train_pool" \
  --checkpoint-dir "$checkpoint_dir" \
  --resume-from "$resume" \
  --seed "$pilot_seed" \
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
  --league-opponent "$anchor" \
  --league-opponent "$anchor" \
  --league-opponent checkpoints/generalized_twentyfourth_robust2_kernel999_lr01_seed15033/policy_v2_repair_step_0050.pt \
  --league-opponent checkpoints/katacr_human_u28_repair3_fresh60701_stage2_seed60702/policy_v2_repair_step_0200.pt \
  --league-opponent checkpoints/human_safety_student6m_u64_safetyrescue_seed1014001/policy_v2_update_000080.pt \
  --league-opponent checkpoints/human_safety_student6m_u80_cleananchor_rescue_seed1015001/policy_v2_update_000112.pt \
  --engine-fast-path on \
  --device mps \
  --actor-device cpu \
  "${trainable_args[@]}" \
  --learning-rate "$learning_rate" \
  --reset-optimizer \
  --gamma 0.995 \
  --gae-lambda 0.95 \
  --clip-ratio 0.2 \
  --value-coef 0 \
  --entropy-coef 0.005 \
  --anchor-checkpoint "$anchor" \
  --anchor-l2-coef 0 \
  --anchor-policy-kl-coef 0.2 \
  --hand-aux-coef 0 \
  --elixir-aux-coef 0 \
  --epochs 2 \
  --sequence-batch-size 2 \
  --target-kl 0.02 \
  --save-every 1 \
  --log-every 1 \
  --no-lr-anneal \
  --quiet-engine \
  2>&1 | tee "reports/${pilot_tag}.log"
