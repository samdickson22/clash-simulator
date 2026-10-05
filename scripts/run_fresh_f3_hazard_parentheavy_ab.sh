#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

source_checkpoint=checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000023.pt
historical=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000010.pt
parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
broad=checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000030.pt
train_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz
pfsp=reports/fresh_f3_hazard_anchor_candidates_seed1069801/update23/strategy.json
selection=reports/fresh_f3_hazard_anchor_candidates_seed1069801/decision.json
root=reports/fresh_f3_hazard_parentheavy_ab_seed1069901
checkpoint_root=checkpoints/fresh_f3_hazard_parentheavy_ab_seed1069901

for required in "$source_checkpoint" "$historical" "$parent" "$broad" \
  "$train_decks" "$corpus" "$sidecar" "$pfsp" "$selection"; do
  [[ -f "$required" ]] || { print -u2 -- "missing parent-heavy input: $required"; exit 1; }
done
[[ $(jq -r '.selected_update' "$selection") == 23 ]] || {
  print -u2 -- "repair anchor selection changed"
  exit 1
}
[[ ! -e "$root/COMPLETE" ]] || { print -u2 -- "refusing completed A/B"; exit 1; }
mkdir -p "$root" "$checkpoint_root"

train_arm() {
  local arm=$1
  local anchor_coef=$2
  local directory="$checkpoint_root/$arm"
  local report="$root/$arm"
  local endpoint="$directory/policy_v2_update_000028.pt"
  [[ ! -e "$endpoint" ]] || { print -u2 -- "refusing existing endpoint: $endpoint"; return 1; }
  mkdir -p "$directory" "$report"
  typeset -a anchor_args
  anchor_args=()
  if [[ "$anchor_coef" != 0 ]]; then
    anchor_args=(--anchor-checkpoint "$source_checkpoint" --anchor-policy-kl-coef "$anchor_coef")
  fi
  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py train -- \
    --decks-path decks.json --sampling-decks-path "$train_decks" \
    --checkpoint-dir "$directory" --resume-from "$source_checkpoint" \
    --seed 1069901 --updates 28 --num-envs 64 --actor-workers 12 --actor-threads 1 \
    --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
    --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
    --opponent-mode league --engine-fast-path on --device mps --actor-device cpu \
    --league-opponent random --league-opponent "$historical" \
    --league-opponent "$parent" --league-opponent "$parent" \
    --league-opponent "$parent" --league-opponent "$broad" \
    --pfsp-report "$pfsp" --pfsp-strategy-workers 6 \
    --learning-rate 2e-5 --gamma 0.995 --gae-lambda 0.95 \
    --clip-ratio 0.2 --value-coef 0.5 --entropy-coef 0.01 \
    --action-type-entropy-coef 0.01 --location-entropy-coef 0.01 \
    --conditional-slot-entropy-coef 0.01 --hand-aux-coef 0 --elixir-aux-coef 0 \
    --epochs 2 --sequence-batch-size 2 --target-kl 0.05 --save-every 1 --log-every 1 \
    --no-lr-anneal --causal-rehearsal-corpus "$corpus" \
    --causal-rehearsal-public-sidecar "$sidecar" \
    --causal-rehearsal-sequence-length 64 --causal-rehearsal-coef 0.125 \
    --causal-rehearsal-batch-sequences 8 "${anchor_args[@]}" --quiet-engine \
    > "$report/train.log" 2>&1
  env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
    --parent "$source_checkpoint" --checkpoint-dir "$directory" \
    --start-update 24 --end-update 28 --max-approx-kl 0.05 \
    --max-anchor-policy-kl 1 --max-clip-fraction 0.30 \
    --output "$report/training_stability.json"
}

train_arm plain 0
train_arm kl005 0.05
print -r -- 'fresh_f3_hazard_parentheavy_ab_complete_v1' > "$root/COMPLETE"
