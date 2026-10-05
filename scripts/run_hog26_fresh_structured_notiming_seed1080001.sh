#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

control=checkpoints/hog26_fresh_structured_notiming_seed1080001/control.pt
checkpoint_root=checkpoints/hog26_fresh_structured_notiming_seed1080001/train
report_root=reports/hog26_fresh_structured_notiming_seed1080001
corpus=datasets/derived/hog26_medium_reactive_dagger_mix2_seed1078601/corpus.npz
sidecar=datasets/derived/hog26_medium_reactive_dagger_mix2_seed1078601/public_v2.npz
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
endpoint="$checkpoint_root/policy_v2_update_000010.pt"

for required in "$control" "$corpus" "$sidecar" "$learner_decks" "$opponent_decks"; do
  [[ -f "$required" ]] || { print -u2 -- "missing no-timing input: $required"; exit 1; }
done
[[ ! -e "$endpoint" ]] || { print -u2 -- "refusing existing no-timing endpoint"; exit 1; }
mkdir -p "$checkpoint_root" "$report_root"

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python scripts/run_clasher.py train -- \
  --decks-path decks.json --sampling-decks-path "$opponent_decks" \
  --learner-sampling-decks-path "$learner_decks" \
  --opponent-sampling-decks-path "$opponent_decks" \
  --checkpoint-dir "$checkpoint_root" --resume-from "$control" \
  --seed 1080001 --updates 10 --num-envs 64 --actor-workers 12 --actor-threads 1 \
  --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
  --opponent-mode league --engine-fast-path on --device mps --actor-device cpu \
  --league-opponent random --league-opponent "$control" \
  --pfsp-report reports/hog26_card_rehearsal_repair_gate_seed1070901/u46_full/strategy.json \
  --pfsp-strategy-workers 10 --learning-rate 0.0001 \
  --gamma 0.995 --gae-lambda 0.95 --clip-ratio 0.2 --value-coef 0.5 \
  --entropy-coef 0.01 --action-type-entropy-coef 0.01 \
  --location-entropy-coef 0.01 --conditional-slot-entropy-coef 0.01 \
  --hand-aux-coef 0 --elixir-aux-coef 0 --epochs 1 --sequence-batch-size 4 \
  --target-kl 0.05 --save-every 1 --log-every 1 --no-lr-anneal \
  --causal-rehearsal-corpus "$corpus" --causal-rehearsal-public-sidecar "$sidecar" \
  --causal-rehearsal-sequence-length 64 --causal-rehearsal-coef 1.0 \
  --causal-rehearsal-decision-coef 0.0 \
  --causal-rehearsal-card-coef 1.0 --causal-rehearsal-tile-coef 0.25 \
  --causal-rehearsal-batch-sequences 16 --quiet-engine \
  > "$report_root/train.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$control" --checkpoint-dir "$checkpoint_root" \
  --start-update 1 --end-update 10 --max-approx-kl 0.05 \
  --max-anchor-policy-kl 0.05 --max-clip-fraction 0.30 \
  --output "$report_root/training_stability.json"
print -r -- 'hog26_fresh_structured_notiming_seed1080001_complete_v1' > "$report_root/COMPLETE"
