#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-python}
initializer=${INITIALIZER:-/home/ubuntu/candidate_play_gate.pt}
output_root=${OUTPUT_ROOT:-checkpoints/hog26_capacity48_cuda_batch_ab_seed1158001}
report_root=${REPORT_ROOT:-reports/hog26_capacity48_cuda_batch_ab_seed1158001}
updates=${UPDATES:-80}
seed=${SEED:-1158001}

for required in \
  "$initializer" \
  training_decks/simple_gym_hog26_supported_v1.json \
  reports/current_client_youtube_stable_vocabulary_v1.json; do
  [[ -f "$required" ]] || { echo "missing required input: $required" >&2; exit 1; }
done

for batch_size in 8 64; do
  checkpoint_dir="$output_root/batch${batch_size}"
  log_path="$report_root/batch${batch_size}.log"
  [[ ! -e "$checkpoint_dir/policy_v2_update_000000.pt" ]] || {
    echo "refusing existing batch-${batch_size} run: $checkpoint_dir" >&2
    exit 1
  }
  mkdir -p "$checkpoint_dir" "$report_root"
  env PYTHONPATH=src:. OMP_NUM_THREADS=2 "$python_bin" \
    -m clasher.rl.train_recurrent \
    --simulation-backend simple-pytorch \
    --simple-supported-decks-path \
      training_decks/simple_gym_hog26_supported_v1.json \
    --simple-max-entities 48 --simple-max-effects 64 \
    --checkpoint-dir "$checkpoint_dir" \
    --initialize-policy-from "$initializer" \
    --seed "$seed" --updates "$updates" \
    --num-envs 128 --actor-workers 1 --actor-threads 2 \
    --rollout-steps 8 --decision-interval 8 --max-ticks 6000 \
    --mirror-match --opponent-mode selfplay \
    --device cuda --actor-device cuda \
    --reward-profile objective-v1 --elixir-leak-penalty-scale 0 \
    --engine-fast-path off \
    --learning-rate 0.0001 --gamma 0.995 --gae-lambda 0.95 \
    --clip-ratio 0.2 --value-coef 0.5 \
    --entropy-coef 0.01 --conditional-slot-entropy-coef 0 \
    --hand-aux-coef 0.02 --elixir-aux-coef 0.05 \
    --epochs 4 --sequence-batch-size "$batch_size" --target-kl 0.03 \
    --save-every 20 --log-every 1 --no-lr-anneal --quiet-engine \
    2>&1 | tee "$log_path"
done
