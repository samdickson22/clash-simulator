#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/fresh_f3_hazard_parentheavy_ab_seed1069901/plain/policy_v2_update_000028.pt
historical=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000010.pt
league_parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
broad=checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000030.pt
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz
pfsp=reports/fresh_f3_hazard_parentheavy_ab_gate_seed1070001/plain/strategy.json
authorization=reports/fresh_f3_hazard_parentheavy_random_confirmation_seed1070101/decision.json
report_root=reports/hog26_specialist_seed1070301
checkpoint_root=checkpoints/hog26_specialist_seed1070301
endpoint="$checkpoint_root/policy_v2_update_000040.pt"

for required in "$parent" "$historical" "$league_parent" "$broad" \
  "$learner_decks" "$opponent_decks" "$corpus" "$sidecar" "$pfsp" \
  "$authorization"; do
  [[ -f "$required" ]] || { print -u2 -- "missing Hog specialist input: $required"; exit 1; }
done
[[ $(jq -r '.selected' "$authorization") == plain ]] || {
  print -u2 -- "parent-heavy confirmation no longer selects plain"
  exit 1
}
[[ $(jq -r '.hog_specialist_curriculum_authorized' "$authorization") == true ]] || {
  print -u2 -- "Hog specialist curriculum is not authorized"
  exit 1
}
[[ ! -e "$endpoint" ]] || { print -u2 -- "refusing existing endpoint: $endpoint"; exit 1; }
[[ ! -e "$report_root/COMPLETE" ]] || { print -u2 -- "refusing completed run"; exit 1; }
mkdir -p "$report_root" "$checkpoint_root"

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python run_clasher.py train -- \
  --decks-path decks.json --sampling-decks-path "$opponent_decks" \
  --learner-sampling-decks-path "$learner_decks" \
  --opponent-sampling-decks-path "$opponent_decks" \
  --checkpoint-dir "$checkpoint_root" --resume-from "$parent" \
  --seed 1070301 --updates 40 --num-envs 64 --actor-workers 12 --actor-threads 1 \
  --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
  --opponent-mode league --engine-fast-path on --device mps --actor-device cpu \
  --league-opponent random --league-opponent "$historical" \
  --league-opponent "$league_parent" --league-opponent "$league_parent" \
  --league-opponent "$broad" \
  --league-opponent "$parent" --pfsp-report "$pfsp" --pfsp-strategy-workers 6 \
  --learning-rate 2e-5 --gamma 0.995 --gae-lambda 0.95 \
  --clip-ratio 0.2 --value-coef 0.5 --entropy-coef 0.01 \
  --action-type-entropy-coef 0.01 --location-entropy-coef 0.01 \
  --conditional-slot-entropy-coef 0.01 --hand-aux-coef 0 --elixir-aux-coef 0 \
  --epochs 2 --sequence-batch-size 2 --target-kl 0.05 --save-every 1 --log-every 1 \
  --no-lr-anneal --causal-rehearsal-corpus "$corpus" \
  --causal-rehearsal-public-sidecar "$sidecar" \
  --causal-rehearsal-sequence-length 64 --causal-rehearsal-coef 0.125 \
  --causal-rehearsal-batch-sequences 8 --quiet-engine \
  > "$report_root/train.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$parent" --checkpoint-dir "$checkpoint_root" \
  --start-update 29 --end-update 40 --max-approx-kl 0.05 \
  --max-anchor-policy-kl 1 --max-clip-fraction 0.30 \
  --output "$report_root/training_stability.json"

print -r -- 'hog26_specialist_seed1070301_complete_v1' > "$report_root/COMPLETE"
