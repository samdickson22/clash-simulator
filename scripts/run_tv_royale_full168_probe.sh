#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

if (( $# != 3 )); then
  print -u2 -r -- "usage: $0 CHECKPOINT PRIORITY_ROOT OUTPUT_ROOT"
  exit 2
fi

checkpoint=$1
priority_root=$2
output_root=$3
baseline_root=reports/evaluations/tv_raw1000_spatial_value_rl_u40_safety
mkdir -p "$output_root"

if [[ ! -f "$checkpoint" ]]; then
  print -u2 -r -- "candidate checkpoint does not exist: $checkpoint"
  exit 1
fi

run_workload() {
  local name=$1
  shift
  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$checkpoint" \
    "$@" \
    --device cpu \
    --reward-profile defense-v2 \
    --json-out "$output_root/${name}.metrics.json" \
    --games-json-out "$output_root/${name}.json" \
    > "$output_root/${name}.log" 2>&1
  PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
    --baseline "$baseline_root/${name}.json" \
    --candidate "$output_root/${name}.json" \
    --output "$output_root/${name}.compare.json"
  print -r -- complete > "$output_root/${name}.ok"
}

run_workload hog_random \
  --opponent random \
  --sampling-decks-path training_decks/katacr_hog26_only.json \
  --games 12 --seed 18601 &
run_workload direct24 \
  --opponent policy \
  --opponent-checkpoint checkpoints/human_safety_tvseq_spatialcore_rl_lr1e6_seed1036008/policy_v2_update_000032_alpha025.pt \
  --games 24 --seed 35201 &
run_workload source36501 \
  --opponent random \
  --games 12 --seed 36501 &
run_workload unseen42501 \
  --opponent random \
  --games 24 --seed 42501 &
run_workload balanced \
  --opponent strategy --opponent-strategy balanced \
  --games 6 --seed 18701 &
run_workload reactive \
  --opponent strategy --opponent-strategy reactive-defense \
  --games 6 --seed 18801 &
run_workload bridge \
  --opponent strategy --opponent-strategy bridge-pressure \
  --games 6 --seed 18901 &
run_workload slow \
  --opponent strategy --opponent-strategy slow-push \
  --games 6 --seed 18951 &
run_workload spell \
  --opponent strategy --opponent-strategy spell-control \
  --games 6 --seed 19001 &
run_workload split \
  --opponent strategy --opponent-strategy split-lane \
  --games 6 --seed 19051 &
wait || true

for name in hog_random direct24 source36501 unseen42501 balanced reactive bridge slow spell split; do
  if [[ ! -f "$output_root/${name}.ok" ]]; then
    print -u2 -r -- "full-screen workload failed: $name"
    exit 1
  fi
done

uv run python - "$priority_root" "$output_root" "$checkpoint" <<'PY'
import json
import sys
from pathlib import Path

priority_root = Path(sys.argv[1])
root = Path(sys.argv[2])
priority_names = ("broad_random", "safety24", "human24")
remaining_names = (
    "hog_random",
    "direct24",
    "source36501",
    "unseen42501",
    "balanced",
    "reactive",
    "bridge",
    "slow",
    "spell",
    "split",
)
comparisons = {
    **{
        name: json.loads((priority_root / f"{name}.compare.json").read_text())
        for name in priority_names
    },
    **{
        name: json.loads((root / f"{name}.compare.json").read_text())
        for name in remaining_names
    },
}
payload = {
    "schema_version": 1,
    "checkpoint": str(Path(sys.argv[3]).resolve()),
    "games": sum(row["games"] for row in comparisons.values()),
    "improvements": sum(row["improvement_count"] for row in comparisons.values()),
    "regressions": sum(row["regression_count"] for row in comparisons.values()),
    "unchanged": sum(row["unchanged_count"] for row in comparisons.values()),
    "crown_difference_change": sum(
        row["crown_difference_change"] for row in comparisons.values()
    ),
    "passes_strict_no_regression": all(
        row["passes_strict_no_regression"] for row in comparisons.values()
    ),
    "workloads": comparisons,
}
(root / "full168_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n"
)
print(json.dumps({"status": "full168_probe_complete", **payload}, sort_keys=True))
PY
