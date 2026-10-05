#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

experiment_seed=${EXPERIMENT_SEED:-1091001}
control=checkpoints/hog26_clean8_simultaneous_seed${experiment_seed}/control.pt
checkpoint_root=checkpoints/hog26_clean8_simultaneous_seed${experiment_seed}/train
report_root=reports/hog26_clean8_simultaneous_seed${experiment_seed}
human_corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
human_sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz
spatial_corpus=datasets/derived/hog26_clean_teacher17_context_seed1090001/corpus.npz
spatial_sidecar=datasets/derived/hog26_clean_teacher17_context_seed1090001/public_v2.npz
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
endpoint="$checkpoint_root/policy_v2_update_000020.pt"

for required in "$control" "$human_corpus" "$human_sidecar" "$spatial_corpus" \
  "$spatial_sidecar" "$learner_decks" "$opponent_decks"; do
  [[ -f "$required" ]] || { print -u2 -- "missing clean8 input: $required"; exit 1; }
done
[[ ! -e "$endpoint" ]] || { print -u2 -- "refusing existing clean8 endpoint"; exit 1; }
mkdir -p "$checkpoint_root" "$report_root"

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python scripts/run_clasher.py train -- \
  --decks-path decks.json --sampling-decks-path "$opponent_decks" \
  --learner-sampling-decks-path "$learner_decks" \
  --opponent-sampling-decks-path "$opponent_decks" \
  --checkpoint-dir "$checkpoint_root" --resume-from "$control" \
  --seed "$experiment_seed" --updates 20 --num-envs 64 --actor-workers 12 --actor-threads 1 \
  --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
  --opponent-mode league --engine-fast-path on --device mps --actor-device cpu \
  --league-opponent random --league-opponent "$control" \
  --pfsp-report reports/hog26_card_rehearsal_repair_gate_seed1070901/u46_full/strategy.json \
  --pfsp-strategy-workers 10 --hazard-conditioned-rollouts \
  --learning-rate 0.0001 --gamma 0.995 --gae-lambda 0.95 --clip-ratio 0.2 \
  --value-coef 0.5 --entropy-coef 0.01 --action-type-entropy-coef 0.01 \
  --location-entropy-coef 0.01 --conditional-slot-entropy-coef 0.01 \
  --hand-aux-coef 0 --elixir-aux-coef 0 --epochs 1 --sequence-batch-size 4 \
  --target-kl 0.05 --save-every 1 --log-every 1 --no-lr-anneal \
  --causal-rehearsal-corpus "$human_corpus" \
  --causal-rehearsal-public-sidecar "$human_sidecar" \
  --causal-rehearsal-sequence-length 64 --causal-rehearsal-coef 0.125 \
  --causal-rehearsal-decision-coef 1.0 \
  --causal-rehearsal-decision-positive-weight 1.0 \
  --causal-rehearsal-card-coef 0.0 --causal-rehearsal-tile-coef 0.0 \
  --causal-rehearsal-batch-sequences 4 \
  --causal-spatial-rehearsal-corpus "$spatial_corpus" \
  --causal-spatial-rehearsal-public-sidecar "$spatial_sidecar" \
  --causal-spatial-rehearsal-sequence-length 64 \
  --causal-spatial-rehearsal-coef 1.0 --causal-spatial-rehearsal-card-coef 1.0 \
  --causal-spatial-rehearsal-tile-coef 0.25 \
  --causal-spatial-rehearsal-batch-sequences 8 --quiet-engine \
  > "$report_root/train.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$control" --checkpoint-dir "$checkpoint_root" \
  --start-update 1 --end-update 20 --max-approx-kl 0.05 \
  --max-anchor-policy-kl 0.05 --max-clip-fraction 0.30 \
  --output "$report_root/training_stability.json"
print -r -- "hog26_clean8_simultaneous_seed${experiment_seed}_complete_v1" \
  > "$report_root/COMPLETE"
