#!/usr/bin/env bash

set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${PYTHON_BIN:-$root/.venv/bin/python}
initializer=${INITIAL_CHECKPOINT:-$root/checkpoints/hog26_factorized_executed_strategy_e3_seed1244001/candidate.pt}
expected_initializer_sha256=${EXPECTED_INITIALIZER_SHA256:-3b651bce56b036b8948eefa0f0b85611c19ac558cbd86e64bece399f23ae3cc5}
output_root=${OUTPUT_ROOT:-$root/reports/hog26_joint_action_value_cuda_ab_seed1246001}
seed=${SEED:-1246001}
updates=${UPDATES:-1}
num_envs=${NUM_ENVS:-28}
rollout_steps=${ROLLOUT_STEPS:-64}

[[ -x "$python_bin" ]] || { echo "missing Python: $python_bin" >&2; exit 1; }
[[ -f "$initializer" ]] || { echo "missing initializer: $initializer" >&2; exit 1; }
[[ ! -e "$output_root" ]] || { echo "refusing to overwrite output: $output_root" >&2; exit 1; }
[[ "$updates" =~ ^[1-9][0-9]*$ ]] || { echo "UPDATES must be positive" >&2; exit 1; }
[[ "$num_envs" =~ ^[1-9][0-9]*$ ]] || { echo "NUM_ENVS must be positive" >&2; exit 1; }
(( num_envs % 2 == 0 )) || { echo "NUM_ENVS must be even" >&2; exit 1; }
[[ "$rollout_steps" =~ ^[1-9][0-9]*$ ]] || { echo "ROLLOUT_STEPS must be positive" >&2; exit 1; }
actual_initializer_sha256=$("$python_bin" - "$initializer" <<'PY'
import hashlib
import sys
from pathlib import Path

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)
[[ "$actual_initializer_sha256" == "$expected_initializer_sha256" ]] || {
  echo "initializer SHA-256 mismatch: expected $expected_initializer_sha256, got $actual_initializer_sha256" >&2
  exit 1
}

mkdir -p "$output_root"

common=(
  --simulation-backend simple-pytorch
  --initialize-policy-from "$initializer"
  --seed "$seed"
  --updates "$updates"
  --num-envs "$num_envs"
  --rollout-steps "$rollout_steps"
  --opponent-mode league
  --league-opponent random
  --league-opponent strategy:balanced
  --league-opponent strategy:bridge-pressure
  --league-opponent strategy:reactive-defense
  --league-opponent strategy:spell-control
  --league-opponent strategy:slow-push
  --league-opponent strategy:split-lane
  --simple-learner-sampling-temperature 0.1
  --device cuda
  --actor-device cuda
  --actor-observation-domain simulator-exact
  --reward-profile objective-v1
  --elixir-leak-penalty-scale 0
  --learning-rate 1e-5
  --epochs 2
  --sequence-batch-size 8
  --entropy-coef 0.001
  --target-kl 0.02
  --no-lr-anneal
  --save-every "$updates"
  --log-every 1
  --quiet-engine
)

for arm in control candidate; do
  checkpoint_dir="$output_root/$arm"
  extra=(--action-value-coef 0)
  if [[ "$arm" == candidate ]]; then
    extra=(--action-value-head --action-value-coef 0.5)
  fi
  env PYTHONPATH="$root/src:$root" OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
    "$python_bin" -m clasher.rl.train_recurrent \
    --checkpoint-dir "$checkpoint_dir" \
    --first-rollout-audit-json "$output_root/$arm.rollout.json" \
    "${common[@]}" "${extra[@]}" \
    > "$output_root/$arm.log" 2>&1
done

env PYTHONPATH="$root/src:$root" "$python_bin" - \
  "$output_root" "$initializer" "$seed" "$updates" "$num_envs" "$rollout_steps" \
  "$expected_initializer_sha256" <<'PY'
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import torch

root = Path(sys.argv[1])
initializer = Path(sys.argv[2]).resolve()
seed = int(sys.argv[3])
updates = int(sys.argv[4])
num_envs = int(sys.argv[5])
rollout_steps = int(sys.argv[6])
expected_initializer_sha256 = sys.argv[7]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_rows(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for line in path.read_text().splitlines():
        if not line.startswith("update="):
            continue
        values: dict[str, float] = {}
        for name in ("tps", "collect_s", "learn_s", "action_q", "q_gate", "play", "noop"):
            match = re.search(rf"(?:^| ){name}=([+\-0-9.eE]+)", line)
            if match is None:
                raise ValueError(f"missing {name} in update log: {line}")
            values[name] = float(match.group(1))
        rows.append(values)
    if len(rows) != updates:
        raise ValueError(f"expected {updates} update rows in {path}, got {len(rows)}")
    return rows


initial: dict[str, dict] = {}
final: dict[str, dict] = {}
logs: dict[str, list[dict[str, float]]] = {}
rollout_audits: dict[str, dict] = {}
for arm in ("control", "candidate"):
    initial_path = root / arm / "policy_v2_update_000000.pt"
    final_path = root / arm / f"policy_v2_update_{updates:06d}.pt"
    if not initial_path.is_file() or not final_path.is_file():
        raise ValueError(f"{arm} did not publish expected checkpoints")
    initial[arm] = torch.load(initial_path, map_location="cpu", weights_only=False)
    final[arm] = torch.load(final_path, map_location="cpu", weights_only=False)
    logs[arm] = update_rows(root / f"{arm}.log")
    rollout_audits[arm] = json.loads((root / f"{arm}.rollout.json").read_text())

for arm, audit in rollout_audits.items():
    if audit.get("schema") != "clasher.pre-optimization-rollout-audit.v1":
        raise ValueError(f"{arm} rollout audit has an unexpected schema")
    if audit.get("update") != 1 or audit.get("seed") != seed:
        raise ValueError(f"{arm} rollout audit has the wrong update or seed")
if rollout_audits["control"]["rollout_sha256"] != rollout_audits["candidate"]["rollout_sha256"]:
    differing_fields = sorted(
        name
        for name in set(rollout_audits["control"]["fields"]) | set(rollout_audits["candidate"]["fields"])
        if rollout_audits["control"]["fields"].get(name)
        != rollout_audits["candidate"]["fields"].get(name)
    )
    raise ValueError(f"pre-optimization rollout mismatch: {differing_fields}")

control_state = initial["control"]["model_state_dict"]
candidate_state = initial["candidate"]["model_state_dict"]
shared = sorted(set(control_state).intersection(candidate_state))
mismatches = [name for name in shared if not torch.equal(control_state[name], candidate_state[name])]
candidate_only = sorted(set(candidate_state).difference(control_state))
if mismatches:
    raise ValueError(f"matched initializers differ on {len(mismatches)} shared tensors")
if len(candidate_only) != 14 or not all(name.startswith("action_value") for name in candidate_only):
    raise ValueError(f"unexpected candidate-only state: {candidate_only}")

for arm in ("control", "candidate"):
    metadata = final[arm].get("simulation_backend_metadata", {})
    if metadata.get("execution_mode") != "cuda-graph":
        raise ValueError(f"{arm} did not use CUDA Graph execution")

control_tps = sum(row["tps"] for row in logs["control"]) / updates
candidate_tps = sum(row["tps"] for row in logs["candidate"]) / updates
throughput_ratio = candidate_tps / control_tps
if throughput_ratio < 0.95:
    status = "rejected-throughput"
elif not all(row["action_q"] > 0.0 for row in logs["candidate"]):
    status = "rejected-action-value-loss"
elif any(row["action_q"] != 0.0 or row["q_gate"] != 0.0 for row in logs["control"]):
    status = "rejected-control-contract"
else:
    status = "passed-device-screen" if updates == 1 else "completed-pilot"

payload = {
    "schema": "clasher.hog26.joint-action-value-cuda-ab.v1",
    "status": status,
    "initializer": str(initializer),
    "initializer_sha256": digest(initializer),
    "expected_initializer_sha256": expected_initializer_sha256,
    "seed": seed,
    "updates": updates,
    "num_envs": num_envs,
    "rollout_steps": rollout_steps,
    "shared_initial_state_entries": len(shared),
    "shared_initial_mismatches": mismatches,
    "candidate_only_state_entries": candidate_only,
    "pre_optimization_rollout_sha256": rollout_audits["control"]["rollout_sha256"],
    "pre_optimization_rollout_fields": rollout_audits["control"]["fields"],
    "control_initial_sha256": digest(root / "control" / "policy_v2_update_000000.pt"),
    "candidate_initial_sha256": digest(root / "candidate" / "policy_v2_update_000000.pt"),
    "control_final_sha256": digest(root / "control" / f"policy_v2_update_{updates:06d}.pt"),
    "candidate_final_sha256": digest(root / "candidate" / f"policy_v2_update_{updates:06d}.pt"),
    "control_updates": logs["control"],
    "candidate_updates": logs["candidate"],
    "mean_control_tps": control_tps,
    "mean_candidate_tps": candidate_tps,
    "candidate_control_throughput_ratio": throughput_ratio,
}
encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
(root / "summary.json").write_text(encoded)
(root / "summary.sha256").write_text(hashlib.sha256(encoded.encode()).hexdigest() + "\n")
(root / "COMPLETE").write_text("hog26_joint_action_value_cuda_ab_complete_v1\n")
print(json.dumps({"status": status, "throughput_ratio": throughput_ratio}, sort_keys=True))
PY
