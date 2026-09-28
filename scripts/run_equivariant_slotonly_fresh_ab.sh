#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/human_safety_equivariant_slotonly_fresh_seed1011001
checkpoint_dir=checkpoints/human_safety_equivariant_slotonly_fresh_seed1011001
checkpoint="$checkpoint_dir/epoch1.pt"

if [[ ! -f reports/human_safety_handperm25_fresh_seed1011001/hand_slot_robustness_hog12.json ]]; then
  print -u2 -- "25-percent mixture evidence is incomplete"
  exit 1
fi
if [[ -e "$root" || -e "$checkpoint_dir" ]]; then
  print -u2 -- "refusing to overwrite existing slot-choice-only experiment"
  exit 1
fi
mkdir -p "$root" "$checkpoint_dir"

env \
  PYTHONUNBUFFERED=1 \
  PYTHONPATH=src:. \
  PYTORCH_ENABLE_MPS_FALLBACK=1 \
  uv run python run_clasher.py imitation -- fit \
    --corpus datasets/human_safety_balanced_v1.npz \
    --output-checkpoint "$checkpoint" \
    --control-checkpoint "$checkpoint_dir/random_control.pt" \
    --manifest-out "$root/manifest.json" \
    --seed 1011001 \
    --split-seed 1011001 \
    --epochs 1 \
    --batch-size 32 \
    --learning-rate 0.00025 \
    --validation-fraction 0.2 \
    --device mps \
    --d-model 192 \
    --num-heads 6 \
    --actor-layers 5 \
    --critic-layers 3 \
    --memory-size 384 \
    --encoder-kind attention \
    --decoder-kind attention \
    --memory-kind lstm \
    --card-input-mode hybrid \
    --card-semantics-version 1 \
    --sequence-length 32 \
    --left-right-augmentation \
    --equivariant-slot-choice-only \
    --imitation-objective spatial-v1 \
    2>&1 | tee "$root/train.log"

env PYTHONPATH=src:. PYTORCH_ENABLE_MPS_FALLBACK=1 \
  uv run python scripts/evaluate_recurrent_corpus.py \
    --corpus datasets/tv_royale_human_chronological_arena28_v1.npz \
    --checkpoint checkpoints/human_safety_legacy_fresh_seed1011001/epoch1.pt \
    --checkpoint checkpoints/human_safety_structural_fresh_seed1011001/epoch1.pt \
    --checkpoint "$checkpoint" \
    --device mps \
    --json-out "$root/chronology_arena28.json" \
    > "$root/chronology_arena28.log" 2>&1

env \
  CLASHER_EQUIVARIANT_CANDIDATE="$checkpoint" \
  CLASHER_EQUIVARIANT_SCREEN_ROOT="$root/gameplay" \
  scripts/run_equivariant_slot_choice_gameplay_screen.sh \
  > "$root/gameplay_screen.log" 2>&1

env PYTHONPATH=src:. \
  uv run python scripts/audit_policy_hand_slot_robustness.py \
    --checkpoint "$checkpoint" \
    --sampling-decks-path training_decks/katacr_hog26_only.json \
    --designated-card HogRider \
    --opponent-strategy balanced \
    --games 12 \
    --seed 1056902 \
    --reward-profile defense-v2 \
    --json-out "$root/hand_slot_robustness_hog12.json" \
    > "$root/hand_slot_robustness_hog12.log" 2>&1

print -r -- '{"status":"equivariant_slotonly_fresh_ab_complete"}'
