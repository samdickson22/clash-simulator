#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-python}
device=${DEVICE:-mps}
corpus_root=${CORPUS_ROOT:-datasets/derived/hog26_parent_terminal_cf_10k_seed1164601}
policy=${POLICY:-checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt}
output_root=${OUTPUT_ROOT:-checkpoints/hog26_action_value_ensemble_seed1164701}
report_root=${REPORT_ROOT:-reports/hog26_action_value_ensemble_seed1164701}
validation_decks=${VALIDATION_DECKS:-datasets/deck_curriculum_v3_seed1056101/validation.json}

for required in \
  "$corpus_root/COMPLETE" \
  "$corpus_root/manifest.json" \
  "$corpus_root/train.npz" \
  "$corpus_root/train.json" \
  "$corpus_root/validation.npz" \
  "$corpus_root/validation.json" \
  "$policy" \
  "$validation_decks"; do
  [[ -f "$required" ]] || {
    echo "missing action-value input: $required" >&2
    exit 1
  }
done
[[ ! -e "$report_root/COMPLETE" && ! -e "$report_root/REJECTED" ]] || {
  echo "refusing finalized action-value run: $report_root" >&2
  exit 1
}
mkdir -p "$output_root" "$report_root"

members=()
for index in 0 1 2; do
  seed=$((1164701 + index))
  checkpoint="$output_root/member_$index.pt"
  report="$report_root/member_$index.json"
  env PYTHONPATH=src:. OMP_NUM_THREADS=2 "$python_bin" \
    scripts/fit_public_action_value.py \
      --corpus "$corpus_root/train.npz" \
      --corpus-report "$corpus_root/train.json" \
      --corpus-manifest "$corpus_root/manifest.json" \
      --source-policy "$policy" \
      --validation-corpus "$corpus_root/validation.npz" \
      --validation-corpus-report "$corpus_root/validation.json" \
      --output "$checkpoint" --report "$report" \
      --seed "$seed" --epochs 300 --patience 40 --batch-size 512 \
      --learning-rate 0.0003 --weight-decay 0.0001 \
      --bootstrap-train-roots \
      --priority-balanced-loss \
      --root-balanced-loss \
      --state-hidden-size 128 --action-hidden-size 128 --hidden-size 128 \
      --torch-threads 2 --device "$device" \
      > "$report_root/member_$index.log" 2>&1
  members+=(--member "$checkpoint")
done

if env PYTHONPATH=src:. OMP_NUM_THREADS=2 "$python_bin" \
  scripts/calibrate_public_action_value_ensemble.py \
    "${members[@]}" \
    --validation-corpus "$corpus_root/validation.npz" \
    --validation-report "$corpus_root/validation.json" \
    --opponent-decks "$validation_decks" \
    --manifest-out "$output_root/ensemble.json" \
    --selection-out "$output_root/controller.json" \
    --report-out "$report_root/calibration.json" \
    --batch-size 512 --torch-threads 2 --device "$device" \
    --minimum-overrides 25 --minimum-pairwise-accuracy 0.65 \
    --minimum-outcome-pairwise-accuracy 0.65 \
    --minimum-outcome-pairs 500 \
    --minimum-regret-reduction 0.25 --minimum-precision-lower 0.75 \
    > "$report_root/calibration.log" 2>&1; then
  printf '%s\n' 'hog26_action_value_ensemble_seed1164701_complete_v1' \
    > "$report_root/COMPLETE"
else
  printf '%s\n' 'hog26_action_value_ensemble_seed1164701_rejected_v1' \
    > "$report_root/REJECTED"
fi
