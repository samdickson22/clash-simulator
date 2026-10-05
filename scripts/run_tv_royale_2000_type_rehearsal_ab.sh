#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt
train_pool=datasets/deck_curriculum_v2_seed1040001/train_without_tv_raw2000_human_meta.json
rehearsal_corpus=datasets/derived/tv_royale_raw_cascade_2000_split_seed1045801/train.npz
root=reports/evaluations/tv_raw2000_type_rehearsal_ab_seed1047201
mkdir -p "$root"

if [[ ! -f "$parent" || ! -f "$train_pool" || ! -f "$rehearsal_corpus" ]]; then
  print -u2 -r -- "missing parent, filtered deck pool, or rehearsal corpus"
  exit 1
fi

names=(control coef00005 coef0001 coef00025)
coefs=(0 0.00005 0.0001 0.00025)

for index in {1..4}; do
  name=${names[$index]}
  coef=${coefs[$index]}
  checkpoint_dir="checkpoints/tv_raw2000_type_rehearsal_${name}_seed1047201"
  candidate="$checkpoint_dir/policy_v2_update_000044.pt"
  log="reports/tv_raw2000_type_rehearsal_${name}_seed1047201.log"
  evidence="$root/$name"
  mkdir -p "$evidence"

  if [[ -e "$candidate" ]]; then
    print -u2 -r -- "refusing stale pilot checkpoint: $candidate"
    exit 1
  fi

  rehearsal_args=()
  if [[ "$coef" != 0 ]]; then
    rehearsal_args=(
      --rehearsal-corpus "$rehearsal_corpus"
      --rehearsal-sequence-length 8
      --rehearsal-coef "$coef"
      --rehearsal-loss-component type
      --rehearsal-batch-sequences 4
    )
  fi

  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py train -- \
    --decks-path decks.json \
    --sampling-decks-path "$train_pool" \
    --checkpoint-dir "$checkpoint_dir" \
    --resume-from "$parent" \
    --seed 1047201 \
    --updates 44 \
    --num-envs 64 \
    --actor-workers 12 \
    --actor-threads 1 \
    --rollout-steps 64 \
    --decision-interval 8 \
    --max-ticks 6000 \
    --reward-profile defense-v2 \
    --opponent-mode league \
    --league-opponent strategy:balanced \
    --league-opponent strategy:reactive-defense \
    --league-opponent strategy:bridge-pressure \
    --league-opponent strategy:slow-push \
    --league-opponent strategy:spell-control \
    --league-opponent strategy:split-lane \
    --league-opponent checkpoints/generalized_twentyfourth_robust2_kernel999_lr01_seed15033/policy_v2_repair_step_0050.pt \
    --league-opponent checkpoints/katacr_human_u28_repair3_fresh60701_stage2_seed60702/policy_v2_repair_step_0200.pt \
    --league-opponent "$parent" \
    --league-opponent "$parent" \
    --league-opponent checkpoints/human_safety_tvseq_spatialcore_rl_lr1e6_seed1036008/policy_v2_update_000032_alpha025.pt \
    --engine-fast-path on \
    --device mps \
    --actor-device cpu \
    --trainable-prefix critic_encoder. \
    --trainable-prefix value_head. \
    --trainable-prefix action_type_head. \
    --learning-rate 1e-6 \
    --reset-optimizer \
    --gamma 0.995 \
    --gae-lambda 0.95 \
    --clip-ratio 0.2 \
    --value-coef 0.5 \
    --entropy-coef 0.01 \
    --anchor-checkpoint "$parent" \
    --anchor-l2-coef 0.01 \
    --anchor-policy-kl-coef 0.2 \
    "${rehearsal_args[@]}" \
    --hand-aux-coef 0 \
    --elixir-aux-coef 0 \
    --epochs 2 \
    --sequence-batch-size 2 \
    --target-kl 0.03 \
    --save-every 1 \
    --log-every 1 \
    --no-lr-anneal \
    --quiet-engine \
    2>&1 | tee "$log"

  if [[ ! -f "$candidate" ]]; then
    print -u2 -r -- "pilot did not publish update 44: $candidate"
    exit 1
  fi

  PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
    --parent "$parent" \
    --checkpoint-dir "$checkpoint_dir" \
    --start-update 41 \
    --end-update 44 \
    --max-approx-kl 0.03 \
    --max-anchor-policy-kl 0.01 \
    --max-clip-fraction 0.20 \
    --output "$evidence/training_stability.json"

  PYTHONPATH=src:. uv run python scripts/audit_rl_state_dict_changes.py \
    --before "$parent" \
    --after "$candidate" \
    --value-prefix critic_encoder. \
    --value-prefix value_head. \
    --actor-prefix action_type_head. \
    --output "$evidence/state_dict_audit.json"
done

print -r -- '{"status":"tv_raw2000_type_rehearsal_ab_complete"}'
