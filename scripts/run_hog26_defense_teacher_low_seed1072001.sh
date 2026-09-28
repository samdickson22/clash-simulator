#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt
historical=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000010.pt
league_parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
broad=checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000030.pt
generalist=checkpoints/fresh_f3_hazard_parentheavy_ab_seed1069901/plain/policy_v2_update_000028.pt
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
teacher_corpus=datasets/derived/hog26_defense_teacher_seed1071701/corpus.npz
teacher_sidecar=datasets/derived/hog26_defense_teacher_seed1071701/public_v2.npz
pfsp=reports/hog26_card_rehearsal_repair_gate_seed1070901/u46_full/strategy.json
report_root=reports/hog26_defense_teacher_low_seed1072001
checkpoint_root=checkpoints/hog26_defense_teacher_low_seed1072001
endpoint="$checkpoint_root/policy_v2_update_000052.pt"

for required in "$parent" "$historical" "$league_parent" "$broad" "$generalist" \
  "$learner_decks" "$opponent_decks" "$teacher_corpus" "$teacher_sidecar" \
  "$pfsp" reports/hog26_defense_teacher_seed1071801/COMPLETE; do
  [[ -f "$required" ]] || { print -u2 -- "missing low-teacher input: $required"; exit 1; }
done
[[ ! -e "$endpoint" ]] || { print -u2 -- "refusing existing endpoint: $endpoint"; exit 1; }
[[ ! -e "$report_root/COMPLETE" ]] || { print -u2 -- "refusing completed low-teacher phase"; exit 1; }
mkdir -p "$report_root" "$checkpoint_root"

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python run_clasher.py train -- \
  --decks-path decks.json --sampling-decks-path "$opponent_decks" \
  --learner-sampling-decks-path "$learner_decks" \
  --opponent-sampling-decks-path "$opponent_decks" \
  --checkpoint-dir "$checkpoint_root" --resume-from "$parent" \
  --seed 1072001 --updates 52 --num-envs 64 --actor-workers 12 --actor-threads 1 \
  --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
  --opponent-mode league --engine-fast-path on --device mps --actor-device cpu \
  --league-opponent random --league-opponent "$historical" \
  --league-opponent "$league_parent" --league-opponent "$league_parent" \
  --league-opponent "$broad" --league-opponent "$generalist" \
  --pfsp-report "$pfsp" --pfsp-strategy-workers 6 \
  --learning-rate 1e-5 --gamma 0.995 --gae-lambda 0.95 \
  --clip-ratio 0.2 --value-coef 0.5 --entropy-coef 0.01 \
  --action-type-entropy-coef 0.01 --location-entropy-coef 0.01 \
  --conditional-slot-entropy-coef 0.01 --hand-aux-coef 0 --elixir-aux-coef 0 \
  --epochs 2 --sequence-batch-size 2 --target-kl 0.05 --save-every 1 --log-every 1 \
  --no-lr-anneal --anchor-checkpoint "$parent" --anchor-policy-kl-coef 0.005 \
  --causal-rehearsal-corpus "$teacher_corpus" \
  --causal-rehearsal-public-sidecar "$teacher_sidecar" \
  --causal-rehearsal-sequence-length 16 --causal-rehearsal-coef 0.01 \
  --causal-rehearsal-card-coef 1.0 --causal-rehearsal-tile-coef 0.25 \
  --causal-rehearsal-batch-sequences 16 --quiet-engine \
  > "$report_root/train.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$parent" --checkpoint-dir "$checkpoint_root" \
  --start-update 47 --end-update 52 --max-approx-kl 0.05 \
  --max-anchor-policy-kl 0.05 --max-clip-fraction 0.30 \
  --output "$report_root/training_stability.json"
print -r -- 'hog26_defense_teacher_low_seed1072001_complete_v1' > "$report_root/COMPLETE"
