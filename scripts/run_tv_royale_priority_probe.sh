#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

if (( $# != 2 )); then
  print -u2 -r -- "usage: $0 CHECKPOINT OUTPUT_ROOT"
  exit 2
fi

checkpoint=$1
output_root=$2
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

run_workload broad_random \
  --opponent random \
  --games 12 \
  --seed 18501 &
run_workload safety24 \
  --opponent policy \
  --opponent-checkpoint checkpoints/generalized_twentyfourth_robust2_kernel999_lr01_seed15033/policy_v2_repair_step_0050.pt \
  --games 24 \
  --seed 35101 &
run_workload human24 \
  --opponent policy \
  --opponent-checkpoint checkpoints/katacr_human_u28_repair3_fresh60701_stage2_seed60702/policy_v2_repair_step_0200.pt \
  --games 24 \
  --seed 35301 &
wait || true

for name in broad_random safety24 human24; do
  if [[ ! -f "$output_root/${name}.ok" ]]; then
    print -u2 -r -- "priority workload failed: $name"
    exit 1
  fi
done

uv run python - "$output_root" "$checkpoint" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
comparisons = {
    name: json.loads((root / f"{name}.compare.json").read_text())
    for name in ("broad_random", "safety24", "human24")
}
payload = {
    "schema_version": 1,
    "checkpoint": str(Path(sys.argv[2]).resolve()),
    "games": sum(row["games"] for row in comparisons.values()),
    "improvements": sum(row["improvement_count"] for row in comparisons.values()),
    "regressions": sum(row["regression_count"] for row in comparisons.values()),
    "crown_difference_change": sum(
        row["crown_difference_change"] for row in comparisons.values()
    ),
    "passes_strict_no_regression": all(
        row["passes_strict_no_regression"] for row in comparisons.values()
    ),
    "workloads": comparisons,
}
(root / "priority_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n"
)
print(json.dumps({"status": "priority_probe_complete", **payload}, sort_keys=True))
PY
