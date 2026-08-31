#!/usr/bin/env python3
"""Compile exact Simple Gym probes into a recurrent repair corpus."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch

PROBE_SCHEMA = "clasher.simple-counterfactual-teacher-probe.v3"
SELECTOR = "hand-slot-spatial-stratified-v1"
RETURN_ESTIMATOR = "truncated-n-step-bootstrap-v1"
CORPUS_SCHEMA = "clasher.hog26.simple-counterfactual-corpus.v2"
ARRAY_KEYS = (
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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pack_entities(arrays: dict[str, np.ndarray]) -> None:
    ids = arrays["entity_ids"]
    features = arrays["entity_features"]
    mask = arrays["entity_mask"]
    packed_ids = np.zeros_like(ids)
    packed_features = np.zeros_like(features)
    packed_mask = np.zeros_like(mask)
    for row in range(mask.shape[0]):
        selected = np.flatnonzero(mask[row])
        count = int(selected.size)
        packed_ids[row, :count] = ids[row, selected]
        packed_features[row, :count] = features[row, selected]
        packed_mask[row, :count] = True
    arrays["entity_ids"] = packed_ids
    arrays["entity_features"] = packed_features
    arrays["entity_mask"] = packed_mask


def _audit_probe(
    path: Path,
    *,
    checkpoint_sha256: str,
    minimum_margin: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(path.read_text())
    if payload.get("schema") != PROBE_SCHEMA:
        raise ValueError(f"probe has unsupported schema: {path}")
    if payload.get("candidate_selector") != SELECTOR:
        raise ValueError(f"probe has unsupported candidate selector: {path}")
    if payload.get("return_estimator") != RETURN_ESTIMATOR:
        raise ValueError(f"probe has unsupported return estimator: {path}")
    opponent = str(payload["opponent_strategy"])
    opponent_randomness = payload.get("opponent_randomness")
    if opponent == "random" and opponent_randomness != "common-quantile-v1":
        raise ValueError(f"random probe has no common-random contract: {path}")
    if opponent != "random" and opponent_randomness not in {
        None,
        "deterministic-strategy",
    }:
        raise ValueError(f"strategy probe has unknown randomness contract: {path}")
    if payload.get("checkpoint_sha256") != checkpoint_sha256:
        raise ValueError(f"probe checkpoint differs from corpus checkpoint: {path}")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError(f"probe has no candidate rows: {path}")
    terminals = np.asarray(
        [row.get("terminal") is True for row in rows],
        dtype=np.bool_,
    )
    if not bool(terminals.all()):
        raise ValueError(f"probe has nonterminal candidate labels: {path}")
    if payload.get("stop_when_all_terminal") is not True:
        raise ValueError(f"probe lacks terminal-stop collection contract: {path}")
    realized_horizon = int(payload.get("realized_horizon_steps", -1))
    declared_horizon = int(payload["horizon_steps"])
    if not 0 < realized_horizon <= declared_horizon:
        raise ValueError(f"probe has invalid realized terminal horizon: {path}")
    actions = np.asarray([int(row["action"]) for row in rows], dtype=np.int64)
    total_scores = np.asarray(
        [float(row["discounted_return_mean"]) for row in rows],
        dtype=np.float64,
    )
    reward_scores = np.asarray(
        [float(row["discounted_reward_return"]) for row in rows],
        dtype=np.float64,
    )
    if (
        len(np.unique(actions)) != len(actions)
        or not np.isfinite(total_scores).all()
        or not np.isfinite(reward_scores).all()
    ):
        raise ValueError(f"probe candidates are duplicated or non-finite: {path}")
    parent_action = int(payload["parent_action"])
    parent_matches = np.flatnonzero(actions == parent_action)
    noop_matches = np.flatnonzero(actions == 2304)
    if parent_matches.size != 1 or noop_matches.size != 1:
        raise ValueError(f"probe must contain parent and no-op exactly once: {path}")
    # The simulator's observed discounted reward is the label authority. The
    # checkpoint critic breaks exact reward ties only and must agree that the
    # selected intervention is not worse than the retained parent/no-op.
    best = int(np.lexsort((total_scores, reward_scores))[-1])
    parent_return = float(total_scores[int(parent_matches[0])])
    noop_return = float(total_scores[int(noop_matches[0])])
    best_return = float(total_scores[best])
    parent_margin = best_return - parent_return
    noop_margin = best_return - noop_return
    parent_reward = float(reward_scores[int(parent_matches[0])])
    noop_reward = float(reward_scores[int(noop_matches[0])])
    best_reward = float(reward_scores[best])
    parent_reward_margin = best_reward - parent_reward
    noop_reward_margin = best_reward - noop_reward
    accepted = bool(
        int(actions[best]) != parent_action
        and parent_reward_margin >= minimum_margin
        and noop_reward_margin >= minimum_margin
        and parent_margin >= 0.0
        and noop_margin >= 0.0
    )
    audit = {
        "probe": path.name,
        "probe_sha256": file_sha256(path),
        "state_sha256": file_sha256(path.with_suffix(".npz")),
        "seed": int(payload["seed"]),
        "opponent": opponent,
        "opponent_randomness": opponent_randomness,
        "warmup_steps": int(payload["warmup_steps"]),
        "declared_horizon_steps": declared_horizon,
        "realized_horizon_steps": realized_horizon,
        "terminal_candidates": int(terminals.sum()),
        "best_action": int(actions[best]),
        "parent_action": parent_action,
        "best_return": best_return,
        "parent_return": parent_return,
        "noop_return": noop_return,
        "parent_margin": parent_margin,
        "noop_margin": noop_margin,
        "best_reward_return": best_reward,
        "parent_reward_return": parent_reward,
        "noop_reward_return": noop_reward,
        "parent_reward_margin": parent_reward_margin,
        "noop_reward_margin": noop_reward_margin,
        "accepted": accepted,
    }
    candidates = {
        "actions": actions,
        "scores": reward_scores,
        "total_scores": total_scores,
        "parent_action": parent_action,
        "best_action": int(actions[best]),
    }
    return audit, candidates


def compile_corpus(
    *,
    probe_root: Path,
    output_root: Path,
    checkpoint: Path,
    minimum_margin: float,
    seed: int,
    workers: int,
    created_at: str,
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite corpus: {output_root}")
    if not 0.0 <= minimum_margin:
        raise ValueError("minimum margin must be nonnegative")
    paths = sorted(probe_root.glob("*.json"))
    if not paths:
        raise ValueError("probe root contains no JSON probes")
    checkpoint = checkpoint.resolve()
    checkpoint_sha256 = file_sha256(checkpoint)
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    token_names = list(payload["token_names"])

    audits: list[dict[str, Any]] = []
    candidates_by_path: dict[Path, dict[str, Any]] = {}
    for path in paths:
        state_path = path.with_suffix(".npz")
        if not state_path.exists():
            raise ValueError(f"probe has no recurrent state archive: {path}")
        audit, candidates = _audit_probe(
            path,
            checkpoint_sha256=checkpoint_sha256,
            minimum_margin=minimum_margin,
        )
        audits.append(audit)
        candidates_by_path[path] = candidates

    parts: dict[str, list[np.ndarray]] = {key: [] for key in ARRAY_KEYS}
    root_rows: list[int] = []
    root_base_actions: list[int] = []
    root_candidate_actions: list[np.ndarray] = []
    root_candidate_scores: list[np.ndarray] = []
    offset = 0
    for path, audit in zip(paths, audits, strict=True):
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as archive:
            missing = sorted(set(ARRAY_KEYS).difference(archive.files))
            if missing:
                raise ValueError(f"probe state is missing arrays {missing}: {path}")
            arrays = {key: archive[key].copy() for key in ARRAY_KEYS}
        row_count = int(arrays["expert_actions"].size)
        expected_rows = int(audit["warmup_steps"]) + 1
        if row_count != expected_rows:
            raise ValueError(f"probe trajectory length changed: {path}")
        candidates = candidates_by_path[path]
        root_mask = arrays["action_masks"][-1]
        if not bool(root_mask[candidates["actions"]].all()):
            raise ValueError(f"probe candidate is illegal at its root: {path}")

        # Behavior distillation always targets what the retained parent did.
        # The better alternative is represented only by the preference table,
        # preventing the behavior loss from silently becoming target leakage.
        arrays["expert_actions"][-1] = int(candidates["parent_action"])
        _pack_entities(arrays)
        for key in ARRAY_KEYS:
            parts[key].append(arrays[key])
        if bool(audit["accepted"]):
            root_rows.append(offset + row_count - 1)
            root_base_actions.append(int(candidates["parent_action"]))
            root_candidate_actions.append(candidates["actions"])
            root_candidate_scores.append(candidates["scores"])
        offset += row_count

    if not root_rows:
        raise ValueError("counterfactual acceptance gate retained zero roots")
    combined = {key: np.concatenate(values, axis=0) for key, values in parts.items()}
    combined["entity_id_confidence"] = combined["entity_mask"].astype(np.float32)
    combined["entity_feature_confidence"] = np.broadcast_to(
        combined["entity_mask"][..., None],
        combined["entity_features"].shape,
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
    zero_crowns = np.zeros(candidate_actions.shape, dtype=np.int16)
    zero_damage = np.zeros(candidate_actions.shape, dtype=np.float64)

    coverage: dict[str, dict[str, int]] = defaultdict(
        lambda: {"probes": 0, "accepted": 0}
    )
    for audit in audits:
        key = f"w{int(audit['warmup_steps']):03d}:{audit['opponent']}"
        coverage[key]["probes"] += 1
        coverage[key]["accepted"] += int(bool(audit["accepted"]))
    action_samples = sorted({len(value["actions"]) for value in candidates_by_path.values()})
    horizons = sorted(
        {int(json.loads(path.read_text())["horizon_steps"]) for path in paths}
    )
    random_fractions = sorted(
        {
            float(json.loads(path.read_text())["random_candidate_fraction"])
            for path in paths
        }
    )
    if len(action_samples) != 1 or len(random_fractions) != 1:
        raise ValueError("probe generation settings are not homogeneous")

    corpus_metadata = {
        "schema_version": 1,
        "created_at": created_at,
        "seed": seed,
        "decisions": int(combined["expert_actions"].size),
        "samples": int(combined["expert_actions"].size),
        "decision_interval": 8,
        "max_ticks": 6000,
        "planner_depth": max(horizons),
        "planner_simulations": 1,
        "planner_action_samples": action_samples[0],
        "max_entities": int(combined["entity_ids"].shape[1]),
        "token_names": token_names,
        "reward_profile": "objective-v1",
        "workers": workers,
        "behavior_checkpoint": str(checkpoint),
        "expert_probability": float(len(root_rows) / len(paths)),
        "stable_root_candidates": True,
        "behavior_opponent": "mixed-strategy-and-random",
        "label_source": "counterfactual-simple-truncated-reward",
        "label_strategy": None,
        "label_checkpoint": str(checkpoint),
        "label_checkpoint_sha256": checkpoint_sha256,
        "sampling_decks_path": None,
    }
    output_root.mkdir(parents=True)
    corpus_path = output_root / "corpus.npz"
    np.savez_compressed(
        corpus_path,
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
    manifest = {
        "schema": CORPUS_SCHEMA,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha256,
        "probe_root": str(probe_root.resolve()),
        "minimum_return_margin": minimum_margin,
        "candidate_selector": SELECTOR,
        "return_estimator": RETURN_ESTIMATOR,
        "preference_score": "discounted_reward_return",
        "label_horizon_contract": "all-candidates-terminal",
        "bootstrap_role": "tie-break-and-nonnegative-consistency-only",
        "all_probe_trajectories_retained_for_behavior": True,
        "root_behavior_action_is_parent": True,
        "probes": len(audits),
        "accepted_probes": len(root_rows),
        "rows": int(combined["expert_actions"].size),
        "supervised_rows": int(combined["expert_action_supervision_valid"].sum()),
        "warmup_steps": sorted({int(audit["warmup_steps"]) for audit in audits}),
        "action_samples": action_samples[0],
        "horizon_steps": horizons,
        "maximum_horizon_steps": max(horizons),
        "random_candidate_fraction": random_fractions[0],
        "coverage": dict(sorted(coverage.items())),
        "corpus": str(corpus_path.resolve()),
        "corpus_sha256": file_sha256(corpus_path),
        "audits": audits,
    }
    encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    (output_root / "manifest.json").write_text(encoded)
    (output_root / "manifest.sha256").write_text(
        hashlib.sha256(encoded.encode()).hexdigest() + "\n"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--minimum-return-margin", type=float, default=0.02)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--created-at", default="2026-08-30T00:00:00+00:00")
    args = parser.parse_args()
    manifest = compile_corpus(
        probe_root=args.probe_root,
        output_root=args.output_root,
        checkpoint=args.checkpoint,
        minimum_margin=args.minimum_return_margin,
        seed=args.seed,
        workers=args.workers,
        created_at=args.created_at,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
