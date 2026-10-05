#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/fresh_f3_outcome_lineage_seed1067501/control.pt
train_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
root=reports/fresh_f3_random_outcome_seed1067701
checkpoint_dir=checkpoints/fresh_f3_random_outcome_seed1067701
candidate="$checkpoint_dir/policy_v2_update_000020.pt"

if [[ -e "$candidate" ]] || [[ -e "$root/training_stability.json" ]]; then
  print -u2 -- "refusing to overwrite F3 random-outcome pilot"
  exit 1
fi
mkdir -p "$root" "$checkpoint_dir"

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py train -- \
  --decks-path decks.json --sampling-decks-path "$train_decks" \
  --checkpoint-dir "$checkpoint_dir" --resume-from "$parent" \
  --seed 1067701 --updates 20 --num-envs 64 --actor-workers 12 --actor-threads 1 \
  --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
  --opponent-mode random --engine-fast-path on --device mps --actor-device cpu \
  --learning-rate 1e-4 --reset-optimizer --gamma 0.995 --gae-lambda 0.95 \
  --clip-ratio 0.2 --value-coef 0.5 --entropy-coef 0.01 \
  --action-type-entropy-coef 0.01 --location-entropy-coef 0.01 \
  --conditional-slot-entropy-coef 0.01 --hand-aux-coef 0 --elixir-aux-coef 0 \
  --epochs 2 --sequence-batch-size 2 --target-kl 0.05 --save-every 1 --log-every 1 \
  --no-lr-anneal --quiet-engine 2>&1 | tee "$root/train.log"

env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$parent" --checkpoint-dir "$checkpoint_dir" --start-update 1 --end-update 20 \
  --max-approx-kl 0.05 --max-anchor-policy-kl 1 --max-clip-fraction 0.30 \
  --output "$root/training_stability.json"

print -r -- '{"status":"fresh_f3_random_outcome_training_complete"}'
