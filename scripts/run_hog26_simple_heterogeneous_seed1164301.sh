#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-python}
initializer=${INITIALIZER:-/workspace/inputs/hog26_champion.pt}
frozen_parent=${FROZEN_PARENT:-$initializer}
output_root=${OUTPUT_ROOT:-checkpoints/hog26_simple_heterogeneous_seed1164301}
report_root=${REPORT_ROOT:-reports/hog26_simple_heterogeneous_seed1164301}
updates=${UPDATES:-120}
seed=${SEED:-1164301}
num_envs=${NUM_ENVS:-64}
rollout_steps=${ROLLOUT_STEPS:-8}
sequence_batch_size=${SEQUENCE_BATCH_SIZE:-64}
save_every=${SAVE_EVERY:-5}
device=${DEVICE:-cuda}
actor_device=${ACTOR_DEVICE:-$device}

minimum_terminal_updates=$(((6000 + 8 * rollout_steps - 1) / (8 * rollout_steps)))
if ((updates < minimum_terminal_updates)); then
  echo "UPDATES=$updates cannot cross the 6000-tick terminal boundary; need >=$minimum_terminal_updates" >&2
  exit 1
fi
if ((num_envs != 64)); then
  echo "NUM_ENVS must remain 64 for the frozen 32-matchup schedule" >&2
  exit 1
fi

for required in \
  "$initializer" \
  "$frozen_parent" \
  training_decks/simple_gym_supported_v1.json \
  reports/current_client_youtube_stable_vocabulary_v1.json; do
  [[ -f "$required" ]] || { echo "missing required input: $required" >&2; exit 1; }
done
[[ ! -e "$output_root/policy_v2_update_000000.pt" ]] || {
  echo "refusing existing run: $output_root" >&2
  exit 1
}

# One item per logical deck matchup. The collector duplicates every item onto
# both physical seats, so opponent kind, opponent deck, and learner seat are
# not confounded. Checkpoint rows are overridden to exact Hog 2.6 mirrors.
league_specs=(
  strategy:bridge-pressure
  strategy:slow-push
  random
  strategy:spell-control
  strategy:reactive-defense
  "$frozen_parent"
  strategy:balanced
  strategy:split-lane
  strategy:bridge-pressure
  "$frozen_parent"
  random
  strategy:slow-push
  strategy:balanced
  strategy:spell-control
  "$frozen_parent"
  strategy:reactive-defense
  strategy:split-lane
  strategy:balanced
  random
  strategy:bridge-pressure
  strategy:slow-push
  strategy:balanced
  strategy:spell-control
  strategy:reactive-defense
  strategy:split-lane
  "$frozen_parent"
  strategy:balanced
  strategy:bridge-pressure
  strategy:balanced
  random
  strategy:balanced
  strategy:balanced
)
if ((${#league_specs[@]} != num_envs / 2)); then
  echo "league schedule must contain one item per logical matchup" >&2
  exit 1
fi
league_args=()
for spec in "${league_specs[@]}"; do
  league_args+=(--league-opponent "$spec")
done

mkdir -p "$output_root" "$report_root"
env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=2 "$python_bin" \
  -m clasher.rl.train_recurrent \
  --simulation-backend simple-pytorch \
  --simple-supported-decks-path training_decks/simple_gym_supported_v1.json \
  --simple-max-entities 56 --simple-max-effects 64 \
  --simple-learner-deck-name 'Hog 2.6 Cycle' \
  --simple-checkpoint-opponent-deck-name 'Hog 2.6 Cycle' \
  --checkpoint-dir "$output_root" \
  --initialize-policy-from "$initializer" \
  --seed "$seed" --updates "$updates" \
  --num-envs "$num_envs" --actor-workers 1 --actor-threads 2 \
  --rollout-steps "$rollout_steps" --decision-interval 8 --max-ticks 6000 \
  --opponent-mode league "${league_args[@]}" \
  --device "$device" --actor-device "$actor_device" \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 0 \
  --engine-fast-path off \
  --learning-rate 0.00001 --gamma 0.995 --gae-lambda 0.95 \
  --clip-ratio 0.2 --value-coef 0.5 --entropy-coef 0.005 \
  --action-type-entropy-coef 0.005 --location-entropy-coef 0.005 \
  --conditional-slot-entropy-coef 0.005 \
  --hand-aux-coef 0 --elixir-aux-coef 0 \
  --epochs 2 --sequence-batch-size "$sequence_batch_size" --target-kl 0.03 \
  --anchor-checkpoint "$initializer" --anchor-policy-kl-coef 0.1 \
  --save-every "$save_every" --log-every 1 --no-lr-anneal --quiet-engine \
  2>&1 | tee "$report_root/train.log"

endpoint="$output_root/policy_v2_update_$(printf '%06d' "$updates").pt"
[[ -f "$endpoint" ]] || { echo "missing terminal checkpoint: $endpoint" >&2; exit 1; }
printf '%s\n' 'hog26_simple_heterogeneous_seed1164301_complete_v1' \
  > "$report_root/COMPLETE"
