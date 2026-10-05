#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/tv_royale_youtube_causal_seed1067001/oracle_gate_f1_clock1500.pt
train_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
development_decks=datasets/deck_curriculum_v3_seed1056101/pfsp_tuning_strict_v2_holdouts.json
validation_decks=datasets/deck_curriculum_v3_seed1056101/validation.json
rehearsal=datasets/derived/fresh_current_client_typed_v1_seed1065401/replay_oracle_mix_152k.npz
human_corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067005/corpus.npz
human_sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067005/public_v2.npz
root=reports/fresh_f1_legacy_replication_seed1067301
checkpoint_dir=checkpoints/fresh_f1_legacy_replication_seed1067301
candidate="$checkpoint_dir/policy_v2_update_000020.pt"

if [[ -e "$root/decision.json" ]] || [[ -e "$candidate" ]]; then
  print -u2 -- "refusing to overwrite legacy replication"
  exit 1
fi
mkdir -p "$root" "$checkpoint_dir"

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py train -- \
  --decks-path decks.json --sampling-decks-path "$train_decks" \
  --checkpoint-dir "$checkpoint_dir" --resume-from "$parent" \
  --seed 1067301 --updates 20 --num-envs 64 --actor-workers 12 --actor-threads 1 \
  --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
  --opponent-mode league \
  --league-opponent random --league-opponent random --league-opponent random \
  --league-opponent strategy:balanced --league-opponent strategy:reactive-defense \
  --league-opponent strategy:bridge-pressure --league-opponent strategy:slow-push \
  --league-opponent strategy:spell-control --league-opponent strategy:split-lane \
  --league-opponent "$parent" --league-opponent "$parent" --league-opponent "$parent" \
  --engine-fast-path on --device mps --actor-device cpu \
  --learning-rate 1e-5 --reset-optimizer --gamma 0.995 --gae-lambda 0.95 \
  --clip-ratio 0.2 --value-coef 0.5 --entropy-coef 0.01 \
  --anchor-checkpoint "$parent" --anchor-l2-coef 0 --anchor-policy-kl-coef 0.5 \
  --anchor-rehearsal-corpus "$rehearsal" --anchor-rehearsal-sequence-length 8 \
  --anchor-rehearsal-coef 0.2 --anchor-rehearsal-batch-sequences 8 \
  --anchor-rehearsal-loss-component joint --hand-aux-coef 0 --elixir-aux-coef 0 \
  --epochs 2 --sequence-batch-size 2 --target-kl 0.03 --save-every 1 --log-every 1 \
  --no-lr-anneal --quiet-engine 2>&1 | tee "$root/train.log"

env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$parent" --checkpoint-dir "$checkpoint_dir" --start-update 1 --end-update 20 \
  --max-approx-kl 0.03 --max-anchor-policy-kl 0.03 --max-clip-fraction 0.25 \
  --output "$root/training_stability.json"

for arm in parent candidate; do
  checkpoint=$parent
  [[ "$arm" == candidate ]] && checkpoint=$candidate
  mkdir -p "$root/$arm"
  env PYTHONPATH=src:. uv run python scripts/run_clasher.py strategy-benchmark -- \
    --checkpoint "$checkpoint" --decks-path decks.json \
    --sampling-decks-path "$development_decks" --games-per-opponent 6 \
    --seed 1067401 --decision-interval 8 --max-ticks 6000 --device cpu \
    --reward-profile objective-v1 --quiet-engine --json-out "$root/$arm/strategy.json" \
    --markdown-out "$root/$arm/strategy.md" > "$root/$arm/strategy.log" 2>&1
  env PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$checkpoint" --opponent random --decks-path decks.json \
    --sampling-decks-path "$development_decks" --games 12 --mirror-match \
    --seed 1067402 --decision-interval 8 --max-ticks 6000 --device cpu \
    --reward-profile objective-v1 --quiet-engine --json-out "$root/$arm/random12.metrics.json" \
    --games-json-out "$root/$arm/random12.games.json" > "$root/$arm/random12.log" 2>&1
  env PYTHONPATH=src:. uv run python scripts/evaluate_recurrent_corpus.py \
    --corpus "$human_corpus" --public-observation-sidecar "$human_sidecar" \
    --checkpoint "$checkpoint" --decks-path decks.json --max-episodes 32 \
    --episode-seed 1067404 --device mps --json-out "$root/$arm/human32.json" \
    > "$root/$arm/human32.log" 2>&1
done

env PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
  --checkpoint "$candidate" --opponent policy --opponent-checkpoint "$parent" \
  --decks-path decks.json --sampling-decks-path "$validation_decks" --games 12 \
  --mirror-match --seed 1067403 --decision-interval 8 --max-ticks 6000 --device cpu \
  --reward-profile objective-v1 --quiet-engine --json-out "$root/candidate/direct12.metrics.json" \
  --games-json-out "$root/candidate/direct12.games.json" > "$root/candidate/direct12.log" 2>&1

env PYTHONPATH=src:. uv run python scripts/finalize_fresh_f1_legacy_replication.py \
  --first-decision reports/fresh_f1_reward_screen_seed1067101/decision.json \
  --root "$root" --output "$root/decision.json" 2>&1 | tee "$root/finalize.log"
