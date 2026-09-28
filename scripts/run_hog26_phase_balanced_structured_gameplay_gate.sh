#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-/Users/sam/Desktop/code/clasher/.venv/bin/python}
device=${DEVICE:-cpu}
policy=${POLICY:-checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt}
ranker_root=${RANKER_ROOT:-checkpoints/hog26_phase_balanced_structured_rankers_v2}
fit_report_root=${FIT_REPORT_ROOT:-reports/hog26_phase_balanced_structured_rankers_v2}
learner_decks=${LEARNER_DECKS:-training_decks/katacr_hog26_only.json}
screen_decks=${SCREEN_DECKS:-datasets/deck_curriculum_v3_seed1056101/heldout_action_value_screen_clean_seed1164811.json}
quarantine_decks=${QUARANTINE_DECKS:-datasets/deck_curriculum_v3_seed1056101/heldout_action_value_quarantine_clean_seed1164811.json}
report_root=${REPORT_ROOT:-reports/hog26_phase_balanced_structured_rankers_v2/gameplay}

for required in \
  "$policy" "$fit_report_root/THREE_SEEDS_COMPLETE" \
  "$fit_report_root/offline_gate.json" "$learner_decks" \
  "$screen_decks" "$quarantine_decks"; do
  [[ -f "$required" ]] || {
    echo "missing phase-balanced structured gameplay input: $required" >&2
    exit 1
  }
done
selected_seed=$("$python_bin" - "$fit_report_root/offline_gate.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("schema") != "clasher.hog26_phase_balanced_structured_ranker_gate.v1":
    raise SystemExit("unexpected structured offline gate")
if payload.get("passed") is not True or payload.get("gameplay_screen_authorized") is not True:
    raise SystemExit("structured offline gate did not authorize gameplay")
print(int(payload["selected_seed"]))
PY
)
ranker="$ranker_root/seed_${selected_seed}.pt"
[[ -f "$ranker" ]] || {
  echo "missing selected structured ranker: $ranker" >&2
  exit 1
}
[[ ! -e "$report_root/COMPLETE" && ! -e "$report_root/REJECTED" ]] || {
  echo "refusing finalized structured gameplay gate: $report_root" >&2
  exit 1
}
mkdir -p "$report_root/screen" "$report_root/quarantine"

strategies=(
  bridge-pressure
  slow-push
  balanced
  reactive-defense
  spell-control
  split-lane
)

run_phase() {
  local phase=$1
  local opponent_decks=$2
  local games=$3
  local seed=$4
  local strategy pid failed
  local -a pids=()
  for strategy in "${strategies[@]}"; do
    env PYTHONPATH=src:. OMP_NUM_THREADS=1 "$python_bin" \
      scripts/eval_action_value_repair.py \
        --policy "$policy" --structured-action-value "$ranker" \
        --decks-path decks.json \
        --learner-sampling-decks-path "$learner_decks" \
        --opponent-sampling-decks-path "$opponent_decks" \
        --strategy "$strategy" --games "$games" --seed "$seed" \
        --decision-interval 8 --max-ticks 6000 --max-candidates 6 \
        --minimum-tick 256 --query-stride 16 \
        --torch-threads 1 --device "$device" \
        --output "$report_root/$phase/$strategy.json" \
        > "$report_root/$phase/$strategy.log" 2>&1 &
    pids+=("$!")
  done
  failed=0
  for pid in "${pids[@]}"; do
    wait "$pid" || failed=1
  done
  ((failed == 0))
}

run_phase screen "$screen_decks" 8 1164811
screen_inputs=()
for strategy in "${strategies[@]}"; do
  screen_inputs+=(--input "$report_root/screen/$strategy.json")
done
if ! env PYTHONPATH=src:. "$python_bin" \
  scripts/finalize_hog26_action_value_ensemble_gate.py \
    "${screen_inputs[@]}" --mode screen \
    --output "$report_root/screen.json"; then
  printf '%s\n' 'hog26_phase_balanced_structured_gameplay_rejected_at_screen_v1' \
    > "$report_root/REJECTED"
  exit 0
fi

run_phase quarantine "$quarantine_decks" 16 1165811
quarantine_inputs=()
for strategy in "${strategies[@]}"; do
  quarantine_inputs+=(--input "$report_root/quarantine/$strategy.json")
done
if ! env PYTHONPATH=src:. "$python_bin" \
  scripts/finalize_hog26_action_value_ensemble_gate.py \
    "${quarantine_inputs[@]}" --mode quarantine \
    --output "$report_root/quarantine.json"; then
  printf '%s\n' 'hog26_phase_balanced_structured_gameplay_rejected_at_quarantine_v1' \
    > "$report_root/REJECTED"
  exit 0
fi

printf '%s\n' 'hog26_phase_balanced_structured_gameplay_complete_v1' \
  > "$report_root/COMPLETE"
