#!/usr/bin/env bash

set -euo pipefail

simple_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${PYTHON_BIN:-/Users/sam/Desktop/code/clasher/.venv/bin/python}
checkpoint=${CHECKPOINT:-$simple_root/checkpoints/hog26_simple_hazard_competence_seed1193001/policy_v2_update_000000.pt}
out=${OUTPUT_ROOT:-$simple_root/datasets/derived/hog26_simple_counterfactual_seed1193501}
seed_base=${SEED_BASE:-1193501}
states_per_opponent=${STATES_PER_OPPONENT:-4}
max_jobs=${MAX_JOBS:-6}
margin=${MINIMUM_RETURN_MARGIN:-0.02}
opponents=(balanced bridge-pressure reactive-defense spell-control slow-push split-lane random)

[[ -e "$python_bin" ]] || { echo "missing Python: $python_bin" >&2; exit 1; }
[[ -e "$checkpoint" ]] || { echo "missing checkpoint: $checkpoint" >&2; exit 1; }
[[ ! -e "$out" ]] || { echo "refusing to overwrite corpus: $out" >&2; exit 1; }
mkdir -p "$out/probes"

pids=()
index=0
for opponent in "${opponents[@]}"; do
  for ((repeat=0; repeat<states_per_opponent; repeat++)); do
    seed=$((seed_base + index))
    stem=$(printf '%02d_%s_%d' "$index" "$opponent" "$seed")
    env PYTHONPATH="$simple_root/src:$simple_root" OMP_NUM_THREADS=1 \
      "$python_bin" "$simple_root/scripts/probe_simple_counterfactual_teacher.py" \
      --checkpoint "$checkpoint" \
      --output "$out/probes/$stem.json" \
      --state-output "$out/probes/$stem.npz" \
      --seed "$seed" --warmup-steps 20 --horizon-steps 24 \
      --action-samples 8 --opponent-strategy "$opponent" --device cpu \
      > "$out/probes/$stem.log" 2>&1 &
    pids+=("$!")
    index=$((index + 1))
    if (( ${#pids[@]} >= max_jobs )); then
      wait "${pids[0]}"
      pids=("${pids[@]:1}")
    fi
  done
done
for pid in "${pids[@]}"; do
  wait "$pid"
done

env PYTHONPATH="$simple_root/src:$simple_root" "$python_bin" - \
  "$out" "$margin" "$checkpoint" <<'PY'
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

root = Path(sys.argv[1])
minimum_margin = float(sys.argv[2])
checkpoint = Path(sys.argv[3]).resolve()
accepted: list[tuple[Path, dict[str, object]]] = []
audits: list[dict[str, object]] = []
for path in sorted((root / "probes").glob("*.json")):
    payload = json.loads(path.read_text())
    rows = payload["rows"]
    by_action = {int(row["action"]): row for row in rows}
    best = rows[0]
    best_action = int(best["action"])
    best_return = float(best["discounted_return_mean"])
    parent_action = int(payload["parent_action"])
    parent_return = float(by_action[parent_action]["discounted_return_mean"])
    noop_return = float(by_action[2304]["discounted_return_mean"])
    parent_margin = best_return - parent_return
    noop_margin = best_return - noop_return
    accept = (
        best_action != parent_action
        and parent_margin >= minimum_margin
        and noop_margin >= minimum_margin
    )
    audit = {
        "probe": str(path.relative_to(root)),
        "probe_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "seed": int(payload["seed"]),
        "opponent": str(payload["opponent_strategy"]),
        "best_action": best_action,
        "parent_action": parent_action,
        "best_return": best_return,
        "parent_return": parent_return,
        "noop_return": noop_return,
        "parent_margin": parent_margin,
        "noop_margin": noop_margin,
        "accepted": accept,
    }
    audits.append(audit)
    if accept:
        accepted.append((path.with_suffix(".npz"), audit))

if not accepted:
    raise RuntimeError("counterfactual acceptance gate retained zero states")
keys = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "hand_ids",
    "global_features",
    "action_masks",
    "previous_actions",
    "previous_rewards",
    "episode_starts",
    "expert_actions",
    "expert_action_supervision_valid",
    "expert_card_supervision_valid",
    "expert_tile_supervision_valid",
    "episode_ids",
    "source_frames",
)
parts: dict[str, list[np.ndarray]] = {key: [] for key in keys}
for path, _audit in accepted:
    with np.load(path, allow_pickle=False) as arrays:
        for key in keys:
            parts[key].append(arrays[key])
combined = {key: np.concatenate(values, axis=0) for key, values in parts.items()}
metadata = {
    "schema": "clasher.hog26.simple-counterfactual-corpus.v1",
    "checkpoint": str(checkpoint),
    "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
    "minimum_return_margin": minimum_margin,
    "probes": len(audits),
    "accepted_probes": len(accepted),
    "rows": int(combined["expert_actions"].size),
    "supervised_rows": int(combined["expert_action_supervision_valid"].sum()),
    "audits": audits,
}
np.savez_compressed(
    root / "corpus.npz",
    **combined,
    metadata_json=np.asarray(json.dumps(metadata, sort_keys=True)),
)
encoded = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
(root / "manifest.json").write_text(encoded)
(root / "manifest.sha256").write_text(
    hashlib.sha256(encoded.encode()).hexdigest() + "\n"
)
PY

printf '%s\n' hog26_simple_counterfactual_corpus_complete_v1 > "$out/COMPLETE"
