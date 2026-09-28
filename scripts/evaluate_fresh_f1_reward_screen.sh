#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=checkpoints/tv_royale_youtube_causal_seed1067001/oracle_gate_f1_clock1500.pt
checkpoint_root=checkpoints/fresh_f1_reward_screen_seed1067101
root=reports/fresh_f1_reward_screen_seed1067101
development_decks=datasets/deck_curriculum_v3_seed1056101/pfsp_tuning_strict_v2_holdouts.json
validation_decks=datasets/deck_curriculum_v3_seed1056101/validation.json
human_corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067005/corpus.npz
human_sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067005/public_v2.npz

if [[ ! -f "$root/train_complete.json" ]]; then
  print -u2 -- "reward-screen training is incomplete"
  exit 1
fi
if [[ -e "$root/decision.json" ]]; then
  print -u2 -- "refusing to overwrite reward-screen decision"
  exit 1
fi

for arm in parent legacy gamma gamma_noleak; do
  if [[ "$arm" == parent ]]; then
    checkpoint=$parent
  else
    checkpoint="$checkpoint_root/$arm/policy_v2_update_000020.pt"
  fi
  arm_root="$root/$arm"
  mkdir -p "$arm_root"

  env PYTHONPATH=src:. uv run python run_clasher.py strategy-benchmark -- \
    --checkpoint "$checkpoint" \
    --decks-path decks.json \
    --sampling-decks-path "$development_decks" \
    --games-per-opponent 6 \
    --seed 1067201 \
    --decision-interval 8 \
    --max-ticks 6000 \
    --device cpu \
    --reward-profile objective-v1 \
    --quiet-engine \
    --json-out "$arm_root/strategy.json" \
    --markdown-out "$arm_root/strategy.md" \
    > "$arm_root/strategy.log" 2>&1

  env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$checkpoint" \
    --opponent random \
    --decks-path decks.json \
    --sampling-decks-path "$development_decks" \
    --games 12 \
    --mirror-match \
    --seed 1067202 \
    --decision-interval 8 \
    --max-ticks 6000 \
    --device cpu \
    --reward-profile objective-v1 \
    --quiet-engine \
    --json-out "$arm_root/random12.metrics.json" \
    --games-json-out "$arm_root/random12.games.json" \
    > "$arm_root/random12.log" 2>&1

  if [[ "$arm" != parent ]]; then
    env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
      --checkpoint "$checkpoint" \
      --opponent policy \
      --opponent-checkpoint "$parent" \
      --decks-path decks.json \
      --sampling-decks-path "$validation_decks" \
      --games 12 \
      --mirror-match \
      --seed 1067203 \
      --decision-interval 8 \
      --max-ticks 6000 \
      --device cpu \
      --reward-profile objective-v1 \
      --quiet-engine \
      --json-out "$arm_root/direct12.metrics.json" \
      --games-json-out "$arm_root/direct12.games.json" \
      > "$arm_root/direct12.log" 2>&1
  fi

  env PYTHONPATH=src:. uv run python scripts/evaluate_recurrent_corpus.py \
    --corpus "$human_corpus" \
    --public-observation-sidecar "$human_sidecar" \
    --checkpoint "$checkpoint" \
    --decks-path decks.json \
    --max-episodes 32 \
    --episode-seed 1067204 \
    --device mps \
    --json-out "$arm_root/human32.json" \
    > "$arm_root/human32.log" 2>&1
done

env PYTHONPATH=src:. uv run python scripts/finalize_fresh_f1_reward_screen.py \
  --root "$root" \
  --checkpoint-root "$checkpoint_root" \
  --parent "$parent" \
  --output "$root/decision.json" \
  2>&1 | tee "$root/finalize.log"
