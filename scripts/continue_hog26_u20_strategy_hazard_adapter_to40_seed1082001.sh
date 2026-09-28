#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/hog26_u20_strategy_hazard_adapter_seed1082001/policy_v2_update_000026.pt
checkpoint_root=checkpoints/hog26_u20_strategy_hazard_adapter_seed1082001
report_root=reports/hog26_u20_strategy_hazard_adapter_seed1082001
timing_corpus=datasets/derived/hog26_medium_reactive_dagger_mix2_seed1078601/corpus.npz
timing_sidecar=datasets/derived/hog26_medium_reactive_dagger_mix2_seed1078601/public_v2.npz
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
endpoint="$checkpoint_root/policy_v2_update_000040.pt"

for required in "$parent" "$timing_corpus" "$timing_sidecar" \
  "$learner_decks" "$opponent_decks"; do
  [[ -f "$required" ]] || { print -u2 -- "missing adapter-continuation input: $required"; exit 1; }
done
[[ ! -e "$endpoint" ]] || { print -u2 -- "refusing existing adapter endpoint"; exit 1; }

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python run_clasher.py train -- \
  --decks-path decks.json --sampling-decks-path "$opponent_decks" \
  --learner-sampling-decks-path "$learner_decks" \
  --opponent-sampling-decks-path "$opponent_decks" \
  --checkpoint-dir "$checkpoint_root" --resume-from "$parent" \
  --seed 1082001 --updates 40 --num-envs 64 --actor-workers 12 --actor-threads 1 \
  --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
  --opponent-mode league --engine-fast-path on --device mps --actor-device cpu \
  --league-opponent random --league-opponent "$parent" \
  --pfsp-report reports/hog26_card_rehearsal_repair_gate_seed1070901/u46_full/strategy.json \
  --pfsp-strategy-workers 10 --reset-optimizer \
  --trainable-prefix play_hazard_adapter. --learning-rate 0.0003 \
  --gamma 0.995 --gae-lambda 0.95 --clip-ratio 0.2 --value-coef 0.5 \
  --entropy-coef 0.01 --action-type-entropy-coef 0.01 \
  --location-entropy-coef 0.01 --conditional-slot-entropy-coef 0.01 \
  --hand-aux-coef 0 --elixir-aux-coef 0 --epochs 1 --sequence-batch-size 4 \
  --target-kl 0.05 --save-every 1 --log-every 1 --no-lr-anneal \
  --causal-rehearsal-corpus "$timing_corpus" \
  --causal-rehearsal-public-sidecar "$timing_sidecar" \
  --causal-rehearsal-sequence-length 64 --causal-rehearsal-coef 1.0 \
  --causal-rehearsal-decision-coef 1.0 \
  --causal-rehearsal-decision-positive-weight 1.0 \
  --causal-rehearsal-card-coef 0.0 --causal-rehearsal-tile-coef 0.0 \
  --causal-rehearsal-batch-sequences 16 --quiet-engine \
  > "$report_root/train_to40.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$parent" --checkpoint-dir "$checkpoint_root" \
  --start-update 27 --end-update 40 --max-approx-kl 0.05 \
  --max-anchor-policy-kl 0.05 --max-clip-fraction 0.30 \
  --output "$report_root/training_stability_to40.json"
print -r -- 'hog26_u20_strategy_hazard_adapter_seed1082001_to40_complete_v1' \
  > "$report_root/COMPLETE_TO40"
