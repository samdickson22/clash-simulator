#!/usr/bin/env bash

set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${PYTHON_BIN:-$root/.venv/bin/python}
initializer=${INITIAL_CHECKPOINT:-$root/checkpoints/hog26_factorized_executed_strategy_e3_seed1244001/candidate.pt}
expected_initializer_sha256=${EXPECTED_INITIALIZER_SHA256:-3b651bce56b036b8948eefa0f0b85611c19ac558cbd86e64bece399f23ae3cc5}
output_root=${OUTPUT_ROOT:-$root/reports/hog26_legacy_joint_q_ab_seed1248201}
seed=${SEED:-1248201}
updates=${UPDATES:-20}
num_envs=${NUM_ENVS:-28}
rollout_steps=${ROLLOUT_STEPS:-64}
actor_workers=${ACTOR_WORKERS:-8}

[[ -x "$python_bin" ]] || { echo "missing Python: $python_bin" >&2; exit 1; }
[[ -f "$initializer" ]] || { echo "missing initializer: $initializer" >&2; exit 1; }
[[ ! -e "$output_root" ]] || { echo "refusing to overwrite output: $output_root" >&2; exit 1; }
for value in "$updates" "$num_envs" "$rollout_steps" "$actor_workers"; do
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || { echo "run dimensions must be positive" >&2; exit 1; }
done
(( actor_workers <= num_envs )) || { echo "ACTOR_WORKERS exceeds NUM_ENVS" >&2; exit 1; }
actual_initializer_sha256=$("$python_bin" - "$initializer" <<'PY'
import hashlib
import sys
from pathlib import Path

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)
[[ "$actual_initializer_sha256" == "$expected_initializer_sha256" ]] || {
  echo "initializer SHA-256 mismatch" >&2
  exit 1
}

mkdir -p "$output_root"
env PYTHONPATH="$root/src:$root" OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  "$python_bin" -m clasher.rl.train_recurrent \
  --simulation-backend simple-pytorch \
  --initialize-policy-from "$initializer" \
  --action-value-head --action-value-coef 0.5 \
  --decks-path "$root/training_decks/simple_gym_hog26_source_v1.json" \
  --checkpoint-dir "$output_root/candidate_initializer" \
  --seed "$seed" --updates 0 --num-envs 2 --rollout-steps 1 \
  --opponent-mode random --simple-learner-sampling-temperature 0.1 \
  --device cpu --actor-device cpu --actor-observation-domain simulator-exact \
  --reward-profile objective-v1 --elixir-leak-penalty-scale 0 \
  --learning-rate 1e-5 --epochs 1 --sequence-batch-size 1 \
  --no-lr-anneal --save-every 1 --quiet-engine \
  > "$output_root/candidate_initializer.log" 2>&1
candidate_initializer="$output_root/candidate_initializer/policy_v2_update_000000.pt"
[[ -f "$candidate_initializer" ]] || { echo "candidate initializer missing" >&2; exit 1; }

common=(
  --simulation-backend python
  --reset-optimizer
  --decks-path "$root/training_decks/simple_gym_hog26_source_v1.json"
  --seed "$seed"
  --updates "$updates"
  --num-envs "$num_envs"
  --rollout-steps "$rollout_steps"
  --actor-workers "$actor_workers"
  --actor-threads 1
  --opponent-mode league
  --league-opponent random
  --league-opponent strategy:balanced
  --league-opponent strategy:bridge-pressure
  --league-opponent strategy:reactive-defense
  --league-opponent strategy:spell-control
  --league-opponent strategy:slow-push
  --league-opponent strategy:split-lane
  --device mps
  --actor-device cpu
  --actor-observation-domain simulator-exact
  --reward-profile objective-v1
  --elixir-leak-penalty-scale 0
  --engine-fast-path on
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
  resume="$initializer"
  extra=(--action-value-coef 0)
  if [[ "$arm" == candidate ]]; then
    resume="$candidate_initializer"
    extra=(--action-value-head --action-value-coef 0.5)
  fi
  env PYTHONPATH="$root/src:$root" OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
    "$python_bin" -m clasher.rl.train_recurrent \
    --resume-from "$resume" \
    --checkpoint-dir "$output_root/$arm" \
    --first-rollout-audit-json "$output_root/$arm.rollout.json" \
    "${common[@]}" "${extra[@]}" \
    > "$output_root/$arm.log" 2>&1
done

env PYTHONPATH="$root/src:$root" "$python_bin" - \
  "$output_root" "$initializer" "$updates" <<'PY'
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import torch

root = Path(sys.argv[1])
initializer = Path(sys.argv[2])
updates = int(sys.argv[3])


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_rows(path: Path) -> list[dict[str, float]]:
    rows = []
    for line in path.read_text().splitlines():
        if not line.startswith("update="):
            continue
        values = {}
        for name in ("tps", "collect_s", "learn_s", "action_q", "q_gate", "play", "noop", "kl"):
            match = re.search(rf"(?:^| ){name}=([+\-0-9.eE]+)", line)
            if match is None:
                raise ValueError(f"missing {name} in {line}")
            values[name] = float(match.group(1))
        rows.append(values)
    if len(rows) != updates:
        raise ValueError(f"expected {updates} update rows, got {len(rows)}")
    return rows


audits = {
    arm: json.loads((root / f"{arm}.rollout.json").read_text())
    for arm in ("control", "candidate")
}
if audits["control"]["rollout_sha256"] != audits["candidate"]["rollout_sha256"]:
    raise ValueError("control and candidate first rollouts differ")

base = torch.load(initializer, map_location="cpu", weights_only=False)["model_state_dict"]
candidate_initial_path = root / "candidate_initializer/policy_v2_update_000000.pt"
candidate_initial = torch.load(
    candidate_initial_path, map_location="cpu", weights_only=False
)["model_state_dict"]
shared = set(base) & set(candidate_initial)
if any(not torch.equal(base[name], candidate_initial[name]) for name in shared):
    raise ValueError("candidate initializer changed shared model tensors")
candidate_only = sorted(set(candidate_initial) - set(base))
if len(candidate_only) != 14 or not all(name.startswith("action_value") for name in candidate_only):
    raise ValueError(f"unexpected candidate-only tensors: {candidate_only}")

logs = {arm: update_rows(root / f"{arm}.log") for arm in ("control", "candidate")}
control_tps = sum(row["tps"] for row in logs["control"]) / updates
candidate_tps = sum(row["tps"] for row in logs["candidate"]) / updates
ratio = candidate_tps / control_tps
if ratio < 0.90:
    status = "rejected-throughput"
elif not all(row["action_q"] > 0.0 for row in logs["candidate"]):
    status = "rejected-action-value-loss"
elif any(row["action_q"] != 0.0 or row["q_gate"] != 0.0 for row in logs["control"]):
    status = "rejected-control-contract"
else:
    status = "completed-local-bridge-pilot"

payload = {
    "schema": "clasher.hog26.legacy-joint-q-ab.v1",
    "status": status,
    "initializer_sha256": digest(initializer),
    "candidate_initializer_sha256": digest(candidate_initial_path),
    "updates": updates,
    "pre_optimization_rollout_sha256": audits["control"]["rollout_sha256"],
    "candidate_only_state_entries": candidate_only,
    "control_updates": logs["control"],
    "candidate_updates": logs["candidate"],
    "mean_control_tps": control_tps,
    "mean_candidate_tps": candidate_tps,
    "candidate_control_throughput_ratio": ratio,
}
encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
(root / "summary.json").write_text(encoded)
(root / "summary.sha256").write_text(hashlib.sha256(encoded.encode()).hexdigest() + "\n")
(root / "COMPLETE").write_text("hog26_legacy_joint_q_ab_complete_v1\n")
print(json.dumps({"status": status, "throughput_ratio": ratio}, sort_keys=True))
PY
