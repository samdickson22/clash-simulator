#!/usr/bin/env bash

set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output_root=${OUTPUT_ROOT:-$root/reports/hog26_joint_action_value_cuda_three_seed}
updates=${UPDATES:-1}

[[ ! -e "$output_root" ]] || { echo "refusing to overwrite output: $output_root" >&2; exit 1; }
mkdir -p "$output_root"

initializer_seeds=(1244001 1244002 1244003)
run_seeds=(1246001 1246002 1246003)
for index in 0 1 2; do
  initializer_seed=${initializer_seeds[$index]}
  run_seed=${run_seeds[$index]}
  INITIAL_CHECKPOINT="$root/checkpoints/hog26_factorized_executed_strategy_e3_seed${initializer_seed}/candidate.pt" \
  OUTPUT_ROOT="$output_root/seed_${run_seed}" \
  SEED="$run_seed" \
  UPDATES="$updates" \
    "$root/scripts/run_hog26_joint_action_value_cuda_ab.sh"
done

"${PYTHON_BIN:-$root/.venv/bin/python}" - "$output_root" "$updates" <<'PY'
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
updates = int(sys.argv[2])
rows = []
for seed in (1246001, 1246002, 1246003):
    path = root / f"seed_{seed}" / "summary.json"
    payload = json.loads(path.read_text())
    rows.append(payload)
expected = "passed-device-screen" if updates == 1 else "completed-pilot"
status = "passed" if all(row["status"] == expected for row in rows) else "rejected"
summary = {
    "schema": "clasher.hog26.joint-action-value-cuda-three-seed.v1",
    "status": status,
    "updates": updates,
    "seeds": [row["seed"] for row in rows],
    "child_statuses": [row["status"] for row in rows],
    "throughput_ratios": [row["candidate_control_throughput_ratio"] for row in rows],
    "minimum_throughput_ratio": min(
        row["candidate_control_throughput_ratio"] for row in rows
    ),
    "children": rows,
}
encoded = json.dumps(summary, indent=2, sort_keys=True) + "\n"
(root / "summary.json").write_text(encoded)
(root / "summary.sha256").write_text(hashlib.sha256(encoded.encode()).hexdigest() + "\n")
if status == "passed":
    (root / "COMPLETE").write_text(
        "hog26_joint_action_value_cuda_three_seed_complete_v1\n"
    )
else:
    raise SystemExit("at least one CUDA seed failed its frozen gate")
print(json.dumps({"status": status, "minimum_throughput_ratio": summary["minimum_throughput_ratio"]}, sort_keys=True))
PY
