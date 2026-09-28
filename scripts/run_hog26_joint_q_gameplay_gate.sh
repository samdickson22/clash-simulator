#!/usr/bin/env bash

set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${PYTHON_BIN:-$root/.venv/bin/python}
pilot_root=${PILOT_ROOT:?set PILOT_ROOT to the completed three-seed CUDA pilot}
output_root=${OUTPUT_ROOT:-$root/reports/hog26_joint_q_gameplay_gate}
update=${UPDATE:-5}
games=${GAMES:-4}
device=${DEVICE:-cuda}
base_seed=${BASE_SEED:-1247001}

[[ -x "$python_bin" ]] || { echo "missing Python: $python_bin" >&2; exit 1; }
[[ -f "$pilot_root/COMPLETE" ]] || { echo "pilot is not complete: $pilot_root" >&2; exit 1; }
[[ ! -e "$output_root" ]] || { echo "refusing to overwrite output: $output_root" >&2; exit 1; }
[[ "$update" =~ ^[1-9][0-9]*$ ]] || { echo "UPDATE must be positive" >&2; exit 1; }
[[ "$games" =~ ^[2-9][0-9]*$|^[2468]$ ]] && (( games % 2 == 0 )) || {
  echo "GAMES must be an even integer >=2" >&2
  exit 1
}
[[ "$device" == cuda || "$device" == cpu || "$device" == mps ]] || {
  echo "DEVICE must be cuda, cpu, or mps" >&2
  exit 1
}

mkdir -p "$output_root"
run_seeds=(1246001 1246002 1246003)
opponents=(bridge-pressure slow-push spell-control reactive-defense split-lane balanced random)
for index in 0 1 2; do
  run_seed=${run_seeds[$index]}
  evaluation_seed=$((base_seed + index * 100000))
  mkdir -p "$output_root/seed_${run_seed}"
  for arm in control candidate; do
    checkpoint="$pilot_root/seed_${run_seed}/$arm/policy_v2_update_$(printf '%06d' "$update").pt"
    [[ -f "$checkpoint" ]] || { echo "missing checkpoint: $checkpoint" >&2; exit 1; }
    opponent_args=()
    for opponent in "${opponents[@]}"; do opponent_args+=(--opponent "$opponent"); done
    env PYTHONPATH="$root/src:$root" "$python_bin" \
      "$root/scripts/evaluate_hog26_simple_policy.py" \
      --checkpoint "$checkpoint" \
      --output "$output_root/seed_${run_seed}/$arm.json" \
      --games "$games" \
      --device "$device" \
      --seed "$evaluation_seed" \
      "${opponent_args[@]}"
  done
done

env PYTHONPATH="$root/src:$root" "$python_bin" \
  "$root/scripts/finalize_hog26_joint_q_gameplay_gate.py" \
  --root "$output_root" --games "$games" --base-seed "$base_seed"
