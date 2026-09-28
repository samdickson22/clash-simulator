#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/hog26_clean8_aligned_seed1095001/calibrated/policy_v2_update_000010_threshold_0p2000.pt
corpus_root=datasets/derived/hog26_clean8_terminal_margin_seed1102001
checkpoint_root=checkpoints/hog26_clean8_terminal_margin_hazard_ab_seed1103001
report_root=reports/hog26_clean8_terminal_margin_hazard_ab_seed1103001

for required in "$parent" "$corpus_root/COMPLETE" \
  "$corpus_root/train_trajectories.npz" \
  "$corpus_root/validation_trajectories.npz"; do
  [[ -f "$required" ]] || { print -u2 -- "missing hazard fit input: $required"; exit 1; }
done
[[ ! -e "$report_root/COMPLETE" ]] || { print -u2 -- "refusing completed hazard A/B"; exit 1; }
mkdir -p "$checkpoint_root" "$report_root"

fit_arm() {
  local arm=$1 behavior_coef=$2 seed=$3
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/train_recurrent_counterfactual_actor.py \
    --initial-checkpoint "$parent" \
    --train-corpus "$corpus_root/train_trajectories.npz" \
    --validation-corpus "$corpus_root/validation_trajectories.npz" \
    --decks-path decks.json \
    --output-checkpoint "$checkpoint_root/$arm.pt" \
    --report "$report_root/$arm.json" --device mps --torch-threads 1 \
    --seed "$seed" --epochs 8 --sequence-length 64 --learning-rate 0.00003 \
    --weight-decay 0.0001 --behavior-coef "$behavior_coef" \
    --counterfactual-coef 1 --root-behavior-weight 0.10 \
    --action-level-preferences --hazard-counterfactual \
    --minimum-crown-gap 1 --minimum-tower-damage-gap 1500 \
    --maximum-hazard-logit-rmse 0.10 --minimum-hazard-safety-accuracy 0.50 \
    --maximum-safety-regression 0.01 --maximum-behavior-regression 0.01 \
    --minimum-corrective-improvement 0.01 --trim-entity-padding \
    --trainable-prefix play_hazard_head. \
    > "$report_root/$arm.log" 2>&1
}

fit_arm conservative_b30 30 1103001
fit_arm balanced_b10 10 1103002
fit_arm assertive_b3 3 1103003

print -r -- 'hog26_clean8_terminal_margin_hazard_ab_seed1103001_complete_v1' \
  > "$report_root/COMPLETE"
