#!/usr/bin/env bash

set -euo pipefail

seed=${1:?usage: run_hog26_hazard_competence.sh SEED}
simple_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
desktop_root=${DESKTOP_ROOT:-/Users/sam/Desktop/code/clasher}
python_bin=${PYTHON_BIN:-$desktop_root/.venv/bin/python}
parent=${PARENT:-$desktop_root/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt}
checkpoint_dir=${CHECKPOINT_DIR:-$simple_root/checkpoints/hog26_simple_hazard_competence_seed${seed}}

for required in "$python_bin" "$parent"; do
  [[ -e "$required" ]] || { echo "missing training input: $required" >&2; exit 1; }
done
[[ ! -e "$checkpoint_dir" ]] || {
  echo "refusing to overwrite existing lineage: $checkpoint_dir" >&2
  exit 1
}

league=(
  random "$parent" random strategy:balanced
  random "$parent" random strategy:slow-push
  "$parent" random strategy:reactive-defense random
  "$parent" random strategy:spell-control "$parent"
  random strategy:bridge-pressure random "$parent"
  random strategy:split-lane "$parent" random
  strategy:balanced random "$parent" random
  strategy:slow-push "$parent" random "$parent"
)

command=(
  "$python_bin" -m clasher.rl.train_recurrent
  --decks-path decks.json
  --simulation-backend simple-pytorch
  --simple-supported-decks-path training_decks/simple_gym_supported_v1.json
  --simple-token-vocabulary-path reports/current_client_youtube_stable_vocabulary_v1.json
  --simple-max-entities 56
  --simple-max-effects 64
  --simple-learner-deck-name "Hog 2.6 Cycle"
  --simple-checkpoint-opponent-deck-name "Hog 2.6 Cycle"
  --simple-learner-sampling-temperature 0.1
  --checkpoint-dir "$checkpoint_dir"
  --initialize-policy-from "$parent"
  --seed "$seed"
  --updates 15
  --num-envs 64
  --actor-workers 1
  --actor-threads 2
  --rollout-steps 64
  --decision-interval 8
  --max-ticks 6000
  --reward-profile objective-v1
  --elixir-leak-penalty-scale 0
  --opponent-mode league
  --engine-fast-path off
  --device mps
  --actor-device mps
  --learning-rate 1e-5
  --gamma 0.995
  --gae-lambda 0.95
  --clip-ratio 0.2
  --value-coef 0.5
  --entropy-coef 0.005
  --action-type-entropy-coef 0.005
  --location-entropy-coef 0.005
  --conditional-slot-entropy-coef 0.005
  --anchor-checkpoint "$parent"
  --anchor-policy-kl-coef 0.1
  --hand-aux-coef 0
  --elixir-aux-coef 0
  --epochs 2
  --sequence-batch-size 8
  --target-kl 0.03
  --save-every 1
  --log-every 1
  --no-lr-anneal
  --quiet-engine
)
for opponent in "${league[@]}"; do
  command+=(--league-opponent "$opponent")
done

cd "$simple_root"
exec env \
  PYTHONUNBUFFERED=1 \
  PYTHONPATH="$simple_root/src:$simple_root" \
  OMP_NUM_THREADS=1 \
  "${command[@]}"
