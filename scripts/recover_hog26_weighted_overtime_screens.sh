#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-/Users/sam/Desktop/code/clasher/.venv/bin/python}
corpus_root=${CORPUS_ROOT:-datasets/derived/hog26_phase_balanced_terminal_cf_v3_seed1175001}
report_root=${REPORT_ROOT:-reports/hog26_phase_balanced_terminal_cf_v3_seed1175001}
recovery_exit=${RECOVERY_EXIT:-$report_root/local_recovery.exit}
policy=${POLICY:-checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt}
learner_decks=${LEARNER_DECKS:-training_decks/katacr_hog26_only.json}
train_decks=${TRAIN_DECKS:-datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json}
validation_decks=${VALIDATION_DECKS:-datasets/deck_curriculum_v3_seed1056101/validation.json}
train_screen=${TRAIN_SCREEN:-reports/hog26_overtime_screen_train_weighted_v2_seed1175001}
validation_screen=${VALIDATION_SCREEN:-reports/hog26_overtime_screen_validation_weighted_v2_seed1181001}

while [[ ! -f "$recovery_exit" ]]; do
  sleep 30
done
status=$(tr -d '[:space:]' < "$recovery_exit")
if [[ -z "$status" || "$status" == 0 ]]; then
  echo "weighted overtime recovery expected the stale v1 run to fail closed" >&2
  exit 1
fi
if [[ -e "$corpus_root/PHASE_BALANCED_COMPLETE" ]]; then
  echo "refusing to rescreen a completed phase-balanced corpus" >&2
  exit 1
fi
for root in "$train_screen" "$validation_screen"; do
  if [[ -e "$root/COMPLETE" ]]; then
    echo "refusing existing weighted overtime screen: $root" >&2
    exit 1
  fi
done

env WORKERS=7 POLICY="$policy" LEARNER_DECKS="$learner_decks" \
  OPPONENT_DECKS="$train_decks" SEED=1175001 GAME_START=500 GAMES=600 \
  OUTPUT_ROOT="$train_screen" PYTHON_BIN="$python_bin" \
  scripts/run_hog26_overtime_screen.sh \
  > "$report_root/weighted_overtime_train_rescreen.log" 2>&1 &
train_pid=$!
env WORKERS=3 POLICY="$policy" LEARNER_DECKS="$learner_decks" \
  OPPONENT_DECKS="$validation_decks" SEED=1181001 GAME_START=150 GAMES=200 \
  OUTPUT_ROOT="$validation_screen" PYTHON_BIN="$python_bin" \
  scripts/run_hog26_overtime_screen.sh \
  > "$report_root/weighted_overtime_validation_rescreen.log" 2>&1 &
validation_pid=$!

failed=0
wait "$train_pid" || failed=1
wait "$validation_pid" || failed=1
((failed == 0)) || exit 1

env PYTHONPATH=src:. "$python_bin" \
  scripts/validate_hog26_overtime_screen_manifest.py \
    --manifest "$train_screen/manifest.json" \
    --policy "$policy" --learner-decks "$learner_decks" \
    --opponent-decks "$train_decks" --selected-count 60 \
    > /dev/null
env PYTHONPATH=src:. "$python_bin" \
  scripts/validate_hog26_overtime_screen_manifest.py \
    --manifest "$validation_screen/manifest.json" \
    --policy "$policy" --learner-decks "$learner_decks" \
    --opponent-decks "$validation_decks" --selected-count 20 \
    > /dev/null

printf '%s\n' hog26_weighted_overtime_rescreens_complete_v2 \
  > "$report_root/WEIGHTED_OVERTIME_RESCREENS_COMPLETE"
