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
warmup_steps_csv=${WARMUP_STEPS:-20}
action_samples=${ACTION_SAMPLES:-8}
horizon_steps=${HORIZON_STEPS:-24}
random_candidate_fraction=${RANDOM_CANDIDATE_FRACTION:-0.25}
probe_root=${PROBE_ROOT:-}
opponents=(balanced bridge-pressure reactive-defense spell-control slow-push split-lane random)
IFS=',' read -r -a warmup_steps_values <<< "$warmup_steps_csv"

[[ -e "$python_bin" ]] || { echo "missing Python: $python_bin" >&2; exit 1; }
[[ -e "$checkpoint" ]] || { echo "missing checkpoint: $checkpoint" >&2; exit 1; }
[[ ! -e "$out" ]] || { echo "refusing to overwrite corpus: $out" >&2; exit 1; }
mkdir -p "$out/probes"

if [[ -n "$probe_root" ]]; then
  [[ -d "$probe_root" ]] || { echo "missing PROBE_ROOT: $probe_root" >&2; exit 1; }
  cp -R "$probe_root"/. "$out/probes"/
else
  pids=()
  index=0
  for warmup_steps in "${warmup_steps_values[@]}"; do
    [[ "$warmup_steps" =~ ^[0-9]+$ ]] || {
      echo "invalid WARMUP_STEPS value: $warmup_steps" >&2
      exit 1
    }
    for opponent in "${opponents[@]}"; do
      for ((repeat=0; repeat<states_per_opponent; repeat++)); do
        seed=$((seed_base + index))
        stem=$(printf '%03d_w%03d_%s_%d' "$index" "$warmup_steps" "$opponent" "$seed")
      env PYTHONPATH="$simple_root/src:$simple_root" OMP_NUM_THREADS=1 \
        "$python_bin" "$simple_root/scripts/probe_simple_counterfactual_teacher.py" \
        --checkpoint "$checkpoint" \
        --output "$out/probes/$stem.json" \
        --state-output "$out/probes/$stem.npz" \
        --seed "$seed" --warmup-steps "$warmup_steps" \
        --horizon-steps "$horizon_steps" --action-samples "$action_samples" \
        --random-candidate-fraction "$random_candidate_fraction" \
        --opponent-strategy "$opponent" --device cpu \
        > "$out/probes/$stem.log" 2>&1 &
        pids+=("$!")
        index=$((index + 1))
        if (( ${#pids[@]} >= max_jobs )); then
          wait "${pids[0]}"
          pids=("${pids[@]:1}")
        fi
      done
    done
  done
  for pid in "${pids[@]}"; do
    wait "$pid"
  done
fi

env PYTHONPATH="$simple_root/src:$simple_root" "$python_bin" - \
  "$out" "$margin" "$checkpoint" "$seed_base" "$max_jobs" \
  "$warmup_steps_csv" "$action_samples" "$horizon_steps" \
  "$random_candidate_fraction" <<'PY'
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

root = Path(sys.argv[1])
minimum_margin = float(sys.argv[2])
checkpoint = Path(sys.argv[3]).resolve()
seed_base = int(sys.argv[4])
worker_count = int(sys.argv[5])
warmup_steps = [int(value) for value in sys.argv[6].split(",")]
action_samples = int(sys.argv[7])
horizon_steps = int(sys.argv[8])
random_candidate_fraction = float(sys.argv[9])
accepted: list[tuple[Path, dict[str, object]]] = []
audits: list[dict[str, object]] = []
for path in sorted((root / "probes").glob("*.json")):
    payload = json.loads(path.read_text())
    if payload.get("schema") != "clasher.simple-counterfactual-teacher-probe.v3":
        raise ValueError(f"probe has unsupported schema: {path}")
    if payload.get("candidate_selector") != "hand-slot-spatial-stratified-v1":
        raise ValueError(f"probe has unsupported candidate selector: {path}")
    if payload.get("return_estimator") != "truncated-n-step-bootstrap-v1":
        raise ValueError(f"probe has unsupported return estimator: {path}")
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
        "warmup_steps": int(payload["warmup_steps"]),
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
root_rows: list[int] = []
root_base_actions: list[int] = []
root_candidate_actions: list[np.ndarray] = []
root_candidate_scores: list[np.ndarray] = []
offset = 0
for path, audit in accepted:
    with np.load(path, allow_pickle=False) as arrays:
        for key in keys:
            parts[key].append(arrays[key])
        row_count = int(arrays["expert_actions"].size)
    probe = json.loads(path.with_suffix(".json").read_text())
    candidate_rows = probe["rows"]
    root_rows.append(offset + row_count - 1)
    root_base_actions.append(int(audit["parent_action"]))
    root_candidate_actions.append(
        np.asarray([int(row["action"]) for row in candidate_rows], dtype=np.int64)
    )
    root_candidate_scores.append(
        np.asarray(
            [float(row["discounted_return_mean"]) for row in candidate_rows],
            dtype=np.float64,
        )
    )
    offset += row_count
combined = {key: np.concatenate(values, axis=0) for key, values in parts.items()}

# Simple Gym owns stable entity slots, including ordinary gaps after deaths.
# Recurrent imitation consumes packed set rows. Stable compaction preserves
# encounter order and every entity feature while moving padding to the suffix.
packed_ids = np.zeros_like(combined["entity_ids"])
packed_features = np.zeros_like(combined["entity_features"])
packed_mask = np.zeros_like(combined["entity_mask"])
for row in range(combined["entity_mask"].shape[0]):
    selected = np.flatnonzero(combined["entity_mask"][row])
    count = int(selected.size)
    packed_ids[row, :count] = combined["entity_ids"][row, selected]
    packed_features[row, :count] = combined["entity_features"][row, selected]
    packed_mask[row, :count] = True
combined["entity_ids"] = packed_ids
combined["entity_features"] = packed_features
combined["entity_mask"] = packed_mask
combined["entity_id_confidence"] = packed_mask.astype(np.float32)
combined["entity_feature_confidence"] = np.broadcast_to(
    packed_mask[..., None], packed_features.shape
).astype(np.float32, copy=True)
combined["hand_id_confidence"] = np.ones(
    combined["hand_ids"].shape, dtype=np.float32
)
combined["global_feature_confidence"] = np.ones(
    combined["global_features"].shape, dtype=np.float32
)
candidate_actions = np.stack(root_candidate_actions)
candidate_scores = np.stack(root_candidate_scores)
candidate_valid = np.ones(candidate_actions.shape, dtype=np.bool_)
hazard_candidate_valid = np.zeros(candidate_actions.shape, dtype=np.bool_)
for root_index in range(candidate_actions.shape[0]):
    base_matches = np.flatnonzero(
        candidate_actions[root_index]
        == np.asarray(root_base_actions)[root_index]
    )
    if base_matches.size != 1:
        raise RuntimeError("hazard corpus requires exactly one parent candidate")
    best = int(np.argmax(candidate_scores[root_index]))
    hazard_candidate_valid[root_index, int(base_matches[0])] = True
    hazard_candidate_valid[root_index, best] = True
zero_crowns = np.zeros(candidate_actions.shape, dtype=np.int16)
zero_damage = np.zeros(candidate_actions.shape, dtype=np.float64)
metadata = {
    "schema": "clasher.hog26.simple-counterfactual-corpus.v1",
    "checkpoint": str(checkpoint),
    "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
    "minimum_return_margin": minimum_margin,
    "warmup_steps": warmup_steps,
    "action_samples": action_samples,
    "horizon_steps": horizon_steps,
    "random_candidate_fraction": random_candidate_fraction,
    "candidate_selector": "hand-slot-spatial-stratified-v1",
    "return_estimator": "truncated-n-step-bootstrap-v1",
    "probes": len(audits),
    "accepted_probes": len(accepted),
    "rows": int(combined["expert_actions"].size),
    "supervised_rows": int(combined["expert_action_supervision_valid"].sum()),
    "audits": audits,
}
checkpoint_payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
corpus_metadata = {
    "schema_version": 1,
    "created_at": "2026-08-29T00:00:00+00:00",
    "seed": seed_base,
    "decisions": int(combined["expert_actions"].size),
    "samples": int(combined["expert_actions"].size),
    "decision_interval": 8,
    "max_ticks": 6000,
    "planner_depth": horizon_steps,
    "planner_simulations": 1,
    "planner_action_samples": int(candidate_actions.shape[1]),
    "max_entities": int(combined["entity_ids"].shape[1]),
    "token_names": list(checkpoint_payload["token_names"]),
    "reward_profile": "objective-v1",
    "workers": worker_count,
    "behavior_checkpoint": str(checkpoint),
    "expert_probability": float(len(accepted) / len(audits)),
    "stable_root_candidates": True,
    "behavior_opponent": "mixed-strategy-and-random",
    "label_source": "counterfactual-simple-nstep-value",
    "label_strategy": None,
    "label_checkpoint": str(checkpoint),
    "label_checkpoint_sha256": metadata["checkpoint_sha256"],
    "sampling_decks_path": None,
}
np.savez_compressed(
    root / "corpus.npz",
    **combined,
    counterfactual_root_rows=np.asarray(root_rows, dtype=np.int64),
    root_base_actions=np.asarray(root_base_actions, dtype=np.int64),
    root_candidate_actions=candidate_actions,
    root_candidate_valid=candidate_valid,
    root_candidate_scores=candidate_scores,
    root_candidate_crown_differences=zero_crowns,
    root_candidate_tower_damage_differences=zero_damage,
    metadata_json=np.asarray(json.dumps(corpus_metadata, sort_keys=True)),
)
np.savez_compressed(
    root / "corpus_hazard.npz",
    **combined,
    counterfactual_root_rows=np.asarray(root_rows, dtype=np.int64),
    root_base_actions=np.asarray(root_base_actions, dtype=np.int64),
    root_candidate_actions=candidate_actions,
    root_candidate_valid=hazard_candidate_valid,
    root_candidate_scores=candidate_scores,
    root_candidate_crown_differences=zero_crowns,
    root_candidate_tower_damage_differences=zero_damage,
    metadata_json=np.asarray(json.dumps(corpus_metadata, sort_keys=True)),
)
encoded = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
(root / "manifest.json").write_text(encoded)
(root / "manifest.sha256").write_text(
    hashlib.sha256(encoded.encode()).hexdigest() + "\n"
)
PY

printf '%s\n' hog26_simple_counterfactual_corpus_complete_v1 > "$out/COMPLETE"
