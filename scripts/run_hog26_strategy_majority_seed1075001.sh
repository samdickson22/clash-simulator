#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt
league_parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
broad=checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000030.pt
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
human_corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
human_sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz
pfsp=reports/hog26_card_rehearsal_repair_gate_seed1070901/u46_full/strategy.json
report_root=reports/hog26_strategy_majority_seed1075001
checkpoint_root=checkpoints/hog26_strategy_majority_seed1075001
endpoint="$checkpoint_root/policy_v2_update_000146.pt"

for required in "$parent" "$league_parent" "$broad" "$learner_decks" \
  "$opponent_decks" "$human_corpus" "$human_sidecar" "$pfsp"; do
  [[ -f "$required" ]] || { print -u2 -- "missing strategy-majority input: $required"; exit 1; }
done
[[ ! -e "$endpoint" ]] || { print -u2 -- "refusing existing endpoint: $endpoint"; exit 1; }
[[ ! -e "$report_root/COMPLETE" ]] || { print -u2 -- "refusing completed strategy-majority phase"; exit 1; }
mkdir -p "$report_root" "$checkpoint_root"

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python run_clasher.py train -- \
  --decks-path decks.json --sampling-decks-path "$opponent_decks" \
  --learner-sampling-decks-path "$learner_decks" \
  --opponent-sampling-decks-path "$opponent_decks" \
  --checkpoint-dir "$checkpoint_root" --resume-from "$parent" \
  --seed 1075001 --updates 146 --num-envs 64 --actor-workers 12 --actor-threads 1 \
  --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
  --opponent-mode league --engine-fast-path on --device mps --actor-device cpu \
  --league-opponent random --league-opponent "$parent" \
  --pfsp-report "$pfsp" --pfsp-strategy-workers 10 \
  --learning-rate 1e-5 --gamma 0.995 --gae-lambda 0.95 \
  --clip-ratio 0.2 --value-coef 0.5 --entropy-coef 0.01 \
  --action-type-entropy-coef 0.01 --location-entropy-coef 0.01 \
  --conditional-slot-entropy-coef 0.01 --hand-aux-coef 0 --elixir-aux-coef 0 \
  --epochs 1 --sequence-batch-size 4 --target-kl 0.05 \
  --save-every 1 --log-every 1 --no-lr-anneal \
  --anchor-checkpoint "$parent" --anchor-policy-kl-coef 0.01 \
  --causal-rehearsal-corpus "$human_corpus" \
  --causal-rehearsal-public-sidecar "$human_sidecar" \
  --causal-rehearsal-sequence-length 64 --causal-rehearsal-coef 0.125 \
  --causal-rehearsal-card-coef 1.0 --causal-rehearsal-batch-sequences 16 \
  --quiet-engine > "$report_root/train.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$parent" --checkpoint-dir "$checkpoint_root" \
  --start-update 47 --end-update 146 --max-approx-kl 0.05 \
  --max-anchor-policy-kl 0.05 --max-clip-fraction 0.30 \
  --output "$report_root/training_stability.json"
print -r -- 'hog26_strategy_majority_seed1075001_complete_v1' > "$report_root/COMPLETE"
