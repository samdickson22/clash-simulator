#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-python}
initializer=${INITIALIZER:-/workspace/inputs/hog26_champion.pt}
output_root=${OUTPUT_ROOT:-checkpoints/hog26_simple_asymmetric_pfsp_seed1163701}
report_root=${REPORT_ROOT:-reports/hog26_simple_asymmetric_pfsp_seed1163701}
updates=${UPDATES:-120}
seed=${SEED:-1163701}
num_envs=${NUM_ENVS:-64}
rollout_steps=${ROLLOUT_STEPS:-8}

minimum_terminal_updates=$(((6000 + 8 * rollout_steps - 1) / (8 * rollout_steps)))
if ((updates < minimum_terminal_updates)); then
  echo "UPDATES=$updates cannot cross the 6000-tick terminal boundary; need >=$minimum_terminal_updates" >&2
  exit 1
fi
if ((num_envs < 2 || num_envs % 2 != 0)); then
  echo "NUM_ENVS must be a positive even number for paired learner seats" >&2
  exit 1
fi

pfsp=reports/hog26_simple_strategy_pfsp_seed1163701.json
for required in \
  "$initializer" \
  "$pfsp" \
  training_decks/simple_gym_supported_v1.json \
  reports/current_client_youtube_stable_vocabulary_v1.json; do
  [[ -f "$required" ]] || { echo "missing required input: $required" >&2; exit 1; }
done
[[ ! -e "$output_root/policy_v2_update_000000.pt" ]] || {
  echo "refusing existing run: $output_root" >&2
  exit 1
}
mkdir -p "$output_root" "$report_root"

env PYTHONPATH=src:. OMP_NUM_THREADS=2 "$python_bin" \
  -m clasher.rl.train_recurrent \
  --simulation-backend simple-pytorch \
  --simple-supported-decks-path training_decks/simple_gym_supported_v1.json \
  --simple-max-entities 56 --simple-max-effects 64 \
  --simple-learner-deck-name 'Hog 2.6 Cycle' \
  --checkpoint-dir "$output_root" \
  --initialize-policy-from "$initializer" \
  --seed "$seed" --updates "$updates" \
  --num-envs "$num_envs" --actor-workers 1 --actor-threads 2 \
  --rollout-steps "$rollout_steps" --decision-interval 8 --max-ticks 6000 \
  --opponent-mode league --pfsp-report "$pfsp" \
  --device cuda --actor-device cuda \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 0 \
  --engine-fast-path off \
  --learning-rate 0.00001 --gamma 0.995 --gae-lambda 0.95 \
  --clip-ratio 0.2 --value-coef 0.5 --entropy-coef 0.005 \
  --action-type-entropy-coef 0.005 --location-entropy-coef 0.005 \
  --conditional-slot-entropy-coef 0.005 \
  --hand-aux-coef 0 --elixir-aux-coef 0 \
  --epochs 2 --sequence-batch-size 64 --target-kl 0.03 \
  --anchor-checkpoint "$initializer" --anchor-policy-kl-coef 0.1 \
  --save-every 20 --log-every 1 --no-lr-anneal --quiet-engine \
  2>&1 | tee "$report_root/train.log"

endpoint="$output_root/policy_v2_update_$(printf '%06d' "$updates").pt"
[[ -f "$endpoint" ]] || { echo "missing terminal checkpoint: $endpoint" >&2; exit 1; }
printf '%s\n' 'hog26_simple_asymmetric_pfsp_seed1163701_complete_v1' \
  > "$report_root/COMPLETE"
