#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=${CLASHER_REACTIVE_REPORT_ROOT:-reports/hog26_small_reactive_teacher17_seed1076201}
checkpoint_root=${CLASHER_REACTIVE_CHECKPOINT_ROOT:-checkpoints/hog26_small_reactive_teacher17_seed1076201}
seed=${CLASHER_REACTIVE_SEED:-1076201}
epochs=${CLASHER_REACTIVE_EPOCHS:-5}
balance_power=${CLASHER_REACTIVE_BALANCE_POWER:-0}
candidate="$checkpoint_root/epoch${epochs}.pt"
control="$checkpoint_root/random_control.pt"
corpus=${CLASHER_REACTIVE_CORPUS:-datasets/derived/hog26_balanced_teacher17_seed1075401/corpus.npz}
sidecar=${CLASHER_REACTIVE_SIDECAR:-datasets/derived/hog26_balanced_teacher17_seed1075401/public_v2.npz}
d_model=${CLASHER_REACTIVE_D_MODEL:-64}
num_heads=${CLASHER_REACTIVE_NUM_HEADS:-4}
actor_layers=${CLASHER_REACTIVE_ACTOR_LAYERS:-2}
critic_layers=${CLASHER_REACTIVE_CRITIC_LAYERS:-1}
memory_size=${CLASHER_REACTIVE_MEMORY_SIZE:-32}
encoder_kind=${CLASHER_REACTIVE_ENCODER_KIND:-attention}

for required in "$corpus" "$sidecar"; do
  [[ -f "$required" ]] || { print -u2 -- "missing reactive-teacher input: $required"; exit 1; }
done
[[ ! -e "$candidate" ]] || { print -u2 -- "refusing existing reactive candidate"; exit 1; }
[[ ! -e "$root/COMPLETE" ]] || { print -u2 -- "refusing completed reactive experiment"; exit 1; }
mkdir -p "$root" "$checkpoint_root"

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. PYTORCH_ENABLE_MPS_FALLBACK=1 \
  uv run python run_clasher.py imitation -- fit \
  --corpus "$corpus" --public-observation-sidecar "$sidecar" \
  --output-checkpoint "$candidate" --control-checkpoint "$control" \
  --manifest-out "$root/manifest.json" --decks-path decks.json \
  --seed "$seed" --split-seed 1076201 --epochs "$epochs" --batch-size 256 \
  --learning-rate 0.0003 --validation-fraction 0.2 --device mps \
  --d-model "$d_model" --num-heads "$num_heads" \
  --actor-layers "$actor_layers" --critic-layers "$critic_layers" \
  --memory-size "$memory_size" --encoder-kind "$encoder_kind" --decoder-kind attention \
  --memory-kind feedforward --card-input-mode residual-hybrid \
  --card-semantics-version 3 --sequence-length 1 --left-right-augmentation \
  --hand-permutation-augmentation --trim-entity-padding \
  --equivariant-hand-policy --imitation-objective hierarchical-v1 \
  --expert-action-type-balance-power "$balance_power" \
  > "$root/train.log" 2>&1

print -r -- 'hog26_small_reactive_teacher17_seed1076201_complete_v1' > "$root/COMPLETE"
