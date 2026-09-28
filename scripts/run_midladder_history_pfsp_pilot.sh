#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

resume=checkpoints/public_history4_rl_seed1046201/policy_v2_update_000045.pt
anchor=checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt
pilot_seed=${PILOT_SEED:-1048602}
learning_rate=${PILOT_LR:-2.5e-6}
end_update=${PILOT_END_UPDATE:-53}
pilot_tag=${PILOT_TAG:-midladder_history_pfsp_nol2_seed1048602}
checkpoint_dir=checkpoints/$pilot_tag
report_root=reports/evaluations/$pilot_tag
train_pool=datasets/deck_curriculum_v2_seed1040001/train_without_tv_raw2000_human_meta.json

mkdir -p "$report_root"

for update in $(seq 46 "$end_update"); do
  checkpoint="$checkpoint_dir/policy_v2_update_$(printf '%06d' "$update").pt"
  if [[ -e "$checkpoint" ]]; then
    print -u2 -r -- "refusing stale bounded-phase checkpoint: $checkpoint"
    exit 1
  fi
done

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
    print -u2 -r -- "missing required pilot input: $required"
    exit 1
  fi
done

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py train -- \
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
  --trainable-prefix public_history_ \
  --trainable-prefix action_type_head. \
  --trainable-prefix critic_encoder. \
  --trainable-prefix value_head. \
  --learning-rate "$learning_rate" \
  --reset-optimizer \
  --gamma 0.995 \
  --gae-lambda 0.95 \
  --clip-ratio 0.2 \
  --value-coef 0.5 \
  --entropy-coef 0.01 \
  --anchor-checkpoint "$anchor" \
  --anchor-l2-coef 0 \
  --anchor-policy-kl-coef 0.2 \
  --hand-aux-coef 0 \
  --elixir-aux-coef 0 \
  --epochs 2 \
  --sequence-batch-size 2 \
  --target-kl 0.03 \
  --save-every 1 \
  --log-every 1 \
  --no-lr-anneal \
  --quiet-engine \
  2>&1 | tee "reports/${pilot_tag}.log"

candidate="$checkpoint_dir/policy_v2_update_$(printf '%06d' "$end_update").pt"
if [[ ! -f "$candidate" ]]; then
  print -u2 -r -- "pilot did not publish endpoint: $candidate"
  exit 1
fi

PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$resume" \
  --checkpoint-dir "$checkpoint_dir" \
  --start-update 46 \
  --end-update "$end_update" \
  --max-approx-kl 0.03 \
  --max-anchor-policy-kl 0.01 \
  --max-clip-fraction 0.20 \
  --output "$report_root/training_stability.json"

PYTHONPATH=src:. uv run python scripts/audit_rl_state_dict_changes.py \
  --before "$resume" \
  --after "$candidate" \
  --actor-prefix public_history_ \
  --actor-prefix action_type_head. \
  --value-prefix critic_encoder. \
  --value-prefix value_head. \
  --output "$report_root/state_dict_audit.json"
