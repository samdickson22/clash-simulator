#!/usr/bin/env bash

set -euo pipefail

simple_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
desktop_root=${DESKTOP_ROOT:-/Users/sam/Desktop/code/clasher}
python_bin=${PYTHON_BIN:-$desktop_root/.venv/bin/python}
parent=${PARENT:-$desktop_root/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt}
candidate=${CANDIDATE:?set CANDIDATE to the checkpoint under evaluation}
out=${OUTPUT_ROOT:?set OUTPUT_ROOT to a fresh report directory}
games=${GAMES:-8}
seed_base=${SEED_BASE:-1193101}
max_jobs=${MAX_JOBS:-6}
candidate_decks=$desktop_root/training_decks/katacr_hog26_only.json
opponent_decks=$desktop_root/datasets/deck_curriculum_v3_seed1056101/heldout_action_value_screen_clean_seed1164811.json
opponents=(balanced bridge-pressure reactive-defense spell-control slow-push split-lane random)

for required in "$python_bin" "$parent" "$candidate" "$candidate_decks" "$opponent_decks"; do
  [[ -e "$required" ]] || { echo "missing promotion input: $required" >&2; exit 1; }
done
[[ ! -e "$out" ]] || { echo "refusing to overwrite promotion output: $out" >&2; exit 1; }
mkdir -p "$out"

run_eval() {
  local checkpoint=$1
  local arm=$2
  local opponent=$3
  local seed=$4
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
    --reward-profile objective-v1 --quiet-engine --games "$games" --seed "$seed" \
    --json-out "$out/$arm-$opponent.metrics.json" \
    --games-json-out "$out/$arm-$opponent.games.json" \
    "${opponent_args[@]}" > "$out/$arm-$opponent.log" 2>&1
}

pids=()
for index in "${!opponents[@]}"; do
  opponent=${opponents[$index]}
  seed=$((seed_base + index))
  for arm in parent candidate; do
    checkpoint=$parent
    [[ "$arm" == candidate ]] && checkpoint=$candidate
    run_eval "$checkpoint" "$arm" "$opponent" "$seed" &
    pids+=("$!")
    if (( ${#pids[@]} >= max_jobs )); then
      wait "${pids[0]}"
      pids=("${pids[@]:1}")
    fi
  done
done
for pid in "${pids[@]}"; do
  wait "$pid"
done

env PYTHONPATH="$desktop_root/src:$desktop_root" "$python_bin" - \
  "$out" "$games" "$seed_base" "${opponents[@]}" <<'PY'
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
games = int(sys.argv[2])
seed_base = int(sys.argv[3])
opponents = sys.argv[4:]
arms: dict[str, object] = {}
for arm in ("parent", "candidate"):
    buckets: dict[str, object] = {}
    total = {"wins": 0, "losses": 0, "draws": 0, "crown_diff": 0.0}
    for opponent in opponents:
        payload = json.loads((root / f"{arm}-{opponent}.metrics.json").read_text())
        metrics = payload["metrics"]
        row = {
            "wins": int(metrics["wins"]),
            "losses": int(metrics["losses"]),
            "draws": int(metrics["draws"]),
            "crown_diff_per_game": float(metrics["crown_diff_per_game"]),
            "placement_rate": float(metrics["candidate_placement_rate"]),
            "defense_success_rate": float(metrics["defense_event_success_rate"]),
        }
        buckets[opponent] = row
        total["wins"] += row["wins"]
        total["losses"] += row["losses"]
        total["draws"] += row["draws"]
        total["crown_diff"] += row["crown_diff_per_game"] * games
    total["crown_diff_per_game"] = total.pop("crown_diff") / (games * len(opponents))
    arms[arm] = {"buckets": buckets, "total": total}

parent_total = arms["parent"]["total"]
candidate_total = arms["candidate"]["total"]
summary = {
    "schema": "clasher.hog26.promotion-matrix.v1",
    "games_per_opponent_arm": games,
    "games_per_arm": games * len(opponents),
    "seed_base": seed_base,
    "opponents": opponents,
    "arms": arms,
    "candidate_minus_parent": {
        "wins": candidate_total["wins"] - parent_total["wins"],
        "losses": candidate_total["losses"] - parent_total["losses"],
        "draws": candidate_total["draws"] - parent_total["draws"],
        "crown_diff_per_game": (
            candidate_total["crown_diff_per_game"]
            - parent_total["crown_diff_per_game"]
        ),
    },
}
encoded = json.dumps(summary, indent=2, sort_keys=True) + "\n"
(root / "summary.json").write_text(encoded)
(root / "summary.sha256").write_text(hashlib.sha256(encoded.encode()).hexdigest() + "\n")
PY

printf '%s\n' hog26_promotion_matrix_complete_v1 > "$out/COMPLETE"
