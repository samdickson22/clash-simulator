#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-/Users/sam/Desktop/code/clasher/.venv/bin/python}
corpus_root=${CORPUS_ROOT:-datasets/derived/hog26_flat_median_counterfactual_quarantine_seed1191001}
runner_exit=${RUNNER_EXIT:-reports/hog26_flat_median_counterfactual_quarantine_runner_seed1191001.exit}
report_root=${REPORT_ROOT:-reports/hog26_phase_balanced_flat_median_dev_v1}

while [[ ! -e "$corpus_root/COMPLETE" ]]; do
  if [[ -e "$runner_exit" ]]; then
    status=$(tr -d '[:space:]' < "$runner_exit")
    if [[ -n "$status" && "$status" != 0 ]]; then
      printf '%s\n' rejected_at_fresh_quarantine_collection \
        > "$report_root/FRESH_QUARANTINE_REJECTED"
      exit 0
    fi
  fi
  sleep 30
done

if env PYTHONPATH=src:. "$python_bin" \
  scripts/audit_hog26_flat_median_fresh_quarantine.py \
    --controller checkpoints/hog26_phase_balanced_flat_median_dev_v1/controller.json \
    --corpus "$corpus_root/quarantine.npz" \
    --policy checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt \
    --decks-path decks.json \
    --contract reports/hog26_flat_median_fresh_quarantine_gate_contract_v1.json \
    --output "$report_root/fresh_counterfactual_quarantine.json" \
    > "$report_root/fresh_counterfactual_quarantine.log" 2>&1; then
  printf '%s\n' hog26_flat_median_fresh_quarantine_passed_v1 \
    > "$report_root/FRESH_QUARANTINE_PASSED"
else
  printf '%s\n' rejected_at_fresh_counterfactual_quarantine \
    > "$report_root/FRESH_QUARANTINE_REJECTED"
fi
