#!/usr/bin/env bash

set -euo pipefail

simple_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
desktop_root=${DESKTOP_ROOT:-/Users/sam/Desktop/code/clasher}
run_root=${RUN_ROOT:-$simple_root/checkpoints/hog26_simple_heterogeneous_long_seed1192001}
report_root=${REPORT_ROOT:-$simple_root/reports/hog26_simple_heterogeneous_long_seed1192001/development_screens}
failure_marker=${FAILURE_MARKER:-$simple_root/reports/hog26_simple_heterogeneous_long_seed1192001/FAILED}
screen_seed_base=${SCREEN_SEED_BASE:-1192001}
boundaries=${BOUNDARIES:-"65 130 255 385 512"}
parent=${PARENT:-$desktop_root/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt}
candidate_decks=${CANDIDATE_DECKS:-$desktop_root/training_decks/katacr_hog26_only.json}
opponent_decks=${OPPONENT_DECKS:-$desktop_root/datasets/deck_curriculum_v3_seed1056101/heldout_action_value_screen_clean_seed1164811.json}
python_bin=${PYTHON_BIN:-$desktop_root/.venv/bin/python}

for required in "$parent" "$candidate_decks" "$opponent_decks" "$python_bin"; do
  [[ -e "$required" ]] || { echo "missing screen input: $required" >&2; exit 1; }
done

mkdir -p "$report_root"

run_one() {
  local checkpoint=$1
  local arm=$2
  local opponent=$3
  local seed=$4
  local out=$5
  local opponent_args=()
  if [[ "$opponent" == random ]]; then
    opponent_args=(--opponent random)
  else
    opponent_args=(--opponent strategy --opponent-strategy "$opponent")
  fi
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH="$desktop_root/src:$desktop_root" OMP_NUM_THREADS=1 \
    "$python_bin" "$desktop_root/scripts/run_clasher.py" eval -- \
    --checkpoint "$checkpoint" --decks-path "$desktop_root/decks.json" \
    --sampling-decks-path "$opponent_decks" \
    --candidate-sampling-decks-path "$candidate_decks" \
    --opponent-sampling-decks-path "$opponent_decks" \
    --decision-interval 8 --max-ticks 6000 --device cpu \
    --reward-profile objective-v1 --quiet-engine --games 4 --seed "$seed" \
    --json-out "$out/$arm-$opponent.metrics.json" \
    --games-json-out "$out/$arm-$opponent.games.json" \
    "${opponent_args[@]}" > "$out/$arm-$opponent.log" 2>&1
}

summarize() {
  local update=$1
  local out=$2
  env PYTHONPATH="$desktop_root/src:$desktop_root" OMP_NUM_THREADS=1 \
    "$python_bin" - "$update" "$out" <<'PY'
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

update = int(sys.argv[1])
root = Path(sys.argv[2])

arms: dict[str, dict[str, object]] = {}
for arm in ("parent", "candidate"):
    buckets: dict[str, object] = {}
    total = {"wins": 0.0, "losses": 0.0, "draws": 0.0, "crown_diff": 0.0}
    for opponent in ("balanced", "bridge-pressure", "random"):
        path = root / f"{arm}-{opponent}.metrics.json"
        payload = json.loads(path.read_text())
        metrics = payload["metrics"]
        row = {
            key: float(metrics[key])
            for key in ("wins", "losses", "draws", "crown_diff_per_game")
        }
        buckets[opponent] = row
        total["wins"] += row["wins"]
        total["losses"] += row["losses"]
        total["draws"] += row["draws"]
        total["crown_diff"] += row["crown_diff_per_game"] * 4.0
    total["crown_diff_per_game"] = total.pop("crown_diff") / 12.0
    arms[arm] = {"buckets": buckets, "total": total}

parent = arms["parent"]["total"]
candidate = arms["candidate"]["total"]
summary = {
    "schema": "clasher.hog26.simple-long-development-screen.v1",
    "update": update,
    "games_per_arm": 12,
    "paired_seats": True,
    "arms": arms,
    "candidate_minus_parent": {
        "wins": candidate["wins"] - parent["wins"],
        "losses": candidate["losses"] - parent["losses"],
        "crown_diff_per_game": (
            candidate["crown_diff_per_game"] - parent["crown_diff_per_game"]
        ),
    },
}
encoded = json.dumps(summary, indent=2, sort_keys=True) + "\n"
(root / "summary.json").write_text(encoded)
(root / "summary.sha256").write_text(
    hashlib.sha256(encoded.encode()).hexdigest() + "\n"
)
PY
}

# Use exact persisted boundaries supplied by the frozen run contract.
for update in $boundaries; do
  padded=$(printf '%06d' "$update")
  checkpoint="$run_root/policy_v2_update_${padded}.pt"
  out="$report_root/update_${padded}"
  while [[ ! -f "$checkpoint" ]]; do
    if [[ -f "$failure_marker" ]]; then
      echo "training failed before update $update" >&2
      exit 1
    fi
    sleep 30
  done
  if [[ -f "$out/COMPLETE" ]]; then
    continue
  fi
  mkdir -p "$out"
  for arm in parent candidate; do
    arm_checkpoint=$parent
    [[ "$arm" == candidate ]] && arm_checkpoint=$checkpoint
    run_one "$arm_checkpoint" "$arm" balanced "$((screen_seed_base + update * 10 + 1))" "$out"
    run_one "$arm_checkpoint" "$arm" bridge-pressure "$((screen_seed_base + update * 10 + 2))" "$out"
    run_one "$arm_checkpoint" "$arm" random "$((screen_seed_base + update * 10 + 3))" "$out"
  done
  summarize "$update" "$out"
  printf '%s\n' "hog26_simple_long_development_screen_update_${padded}_complete_v1" > "$out/COMPLETE"
done

printf '%s\n' hog26_simple_long_development_screens_complete_v1 > "$report_root/COMPLETE"
