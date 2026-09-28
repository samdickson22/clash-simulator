#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

seed=1067901
development=datasets/deck_curriculum_v3_seed1056101/pfsp_tuning_strict_v2_holdouts.json
corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz
screen_root=reports/fresh_f3_causal_rehearsal_screen_seed${seed}
mkdir -p "$screen_root"
[[ ! -e "$screen_root/decision.json" ]] || { print -u2 -- "refusing existing decision"; exit 1; }

for arm in parent 0010 0025; do
  case "$arm" in
    parent)
      checkpoint=checkpoints/fresh_f3_outcome_lineage_seed1067501/control.pt
      arm_root="$screen_root/parent"
      ;;
    *)
      checkpoint=checkpoints/fresh_f3_causal_rehearsal_${arm}_seed${seed}/policy_v2_update_000010.pt
      arm_root="$screen_root/$arm"
      ;;
  esac
  [[ -f "$checkpoint" ]] || { print -u2 -- "missing screen checkpoint: $checkpoint"; exit 1; }
  mkdir -p "$arm_root"
  env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$checkpoint" --opponent random --decks-path decks.json \
    --sampling-decks-path "$development" --games 12 --mirror-match --seed 1067902 \
    --decision-interval 8 --max-ticks 6000 --device cpu --reward-profile objective-v1 \
    --quiet-engine --json-out "$arm_root/random12.metrics.json" \
    --games-json-out "$arm_root/random12.games.json" > "$arm_root/random12.log" 2>&1
  env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$checkpoint" --opponent strategy --opponent-strategy balanced \
    --decks-path decks.json --sampling-decks-path "$development" --games 12 \
    --mirror-match --seed 1067903 --decision-interval 8 --max-ticks 6000 \
    --device cpu --reward-profile objective-v1 --quiet-engine \
    --json-out "$arm_root/balanced12.metrics.json" \
    --games-json-out "$arm_root/balanced12.games.json" > "$arm_root/balanced12.log" 2>&1
  env PYTHONPATH=src:. uv run python scripts/evaluate_recurrent_corpus.py \
    --corpus "$corpus" --public-observation-sidecar "$sidecar" \
    --checkpoint "$checkpoint" --decks-path decks.json --max-episodes 64 \
    --episode-seed 1067904 --device mps --json-out "$arm_root/human64.json" \
    > "$arm_root/human64.log" 2>&1
done

env PYTHONPATH=src:. uv run python scripts/finalize_fresh_f3_causal_rehearsal_screen.py \
  --root "$screen_root" --output "$screen_root/decision.json" \
  2>&1 | tee "$screen_root/finalize.log"
