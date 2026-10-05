#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/fresh_f3_outcome_lineage_seed1067501/control.pt
train_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz
seed=1067901

for required in "$parent" "$train_decks" "$corpus" "$sidecar"; do
  [[ -f "$required" ]] || { print -u2 -- "missing causal rehearsal input: $required"; exit 1; }
done

for coefficient in 0010 0025; do
  case "$coefficient" in
    0010) value=0.01 ;;
    0025) value=0.025 ;;
  esac
  root=reports/fresh_f3_causal_rehearsal_${coefficient}_seed${seed}
  checkpoint_dir=checkpoints/fresh_f3_causal_rehearsal_${coefficient}_seed${seed}
  candidate="$checkpoint_dir/policy_v2_update_000010.pt"
  [[ ! -e "$candidate" ]] || { print -u2 -- "refusing existing candidate: $candidate"; exit 1; }
  mkdir -p "$root" "$checkpoint_dir"

  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py train -- \
    --decks-path decks.json --sampling-decks-path "$train_decks" \
    --checkpoint-dir "$checkpoint_dir" --resume-from "$parent" \
    --seed "$seed" --updates 10 --num-envs 64 --actor-workers 12 --actor-threads 1 \
    --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
    --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
    --opponent-mode random --engine-fast-path on --device mps --actor-device cpu \
    --learning-rate 1e-4 --reset-optimizer --gamma 0.995 --gae-lambda 0.95 \
    --clip-ratio 0.2 --value-coef 0.5 --entropy-coef 0.01 \
    --action-type-entropy-coef 0.01 --location-entropy-coef 0.01 \
    --conditional-slot-entropy-coef 0.01 --hand-aux-coef 0 --elixir-aux-coef 0 \
    --epochs 2 --sequence-batch-size 2 --target-kl 0.05 --save-every 1 --log-every 1 \
    --no-lr-anneal --causal-rehearsal-corpus "$corpus" \
    --causal-rehearsal-public-sidecar "$sidecar" \
    --causal-rehearsal-sequence-length 64 --causal-rehearsal-coef "$value" \
    --causal-rehearsal-batch-sequences 1 --quiet-engine 2>&1 | tee "$root/train.log"

  env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
    --parent "$parent" --checkpoint-dir "$checkpoint_dir" \
    --start-update 1 --end-update 10 --max-approx-kl 0.05 \
    --max-anchor-policy-kl 1 --max-clip-fraction 0.30 \
    --output "$root/training_stability.json"
done

print -r -- '{"status":"fresh_f3_causal_rehearsal_screen_complete"}'
