#!/usr/bin/env python3
"""Evaluate one frozen terminal reranker on an untouched probe split."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

import torch

from clasher.rl.terminal_action_reranker import TerminalActionReranker
from scripts.train_hog26_factorized_counterfactual import file_sha256
from scripts.train_hog26_terminal_reranker import (
    REPORT_SCHEMA,
    _load_policy,
    evaluate_reranker,
    fixed_threshold_root_details,
    load_probe_examples,
)

EVALUATION_SCHEMA = "clasher.hog26.terminal-action-reranker-holdout.v1"


def fixed_threshold_row(metrics: dict[str, Any], threshold: float) -> dict[str, Any]:
    matches = [
        row
        for row in metrics["threshold_curve"]
        if abs(float(row["threshold"]) - threshold) < 1e-12
    ]
    if len(matches) != 1:
        raise ValueError("frozen override threshold is absent or duplicated")
    return cast(dict[str, Any], matches[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-checkpoint", type=Path, required=True)
    parser.add_argument("--reranker-checkpoint", type=Path, required=True)
    parser.add_argument("--train-probes", type=Path, required=True)
    parser.add_argument("--development-probes", type=Path, required=True)
    parser.add_argument("--holdout-probes", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--minimum-improvements", type=int, default=2)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit("refusing to overwrite terminal reranker evaluation")
    if args.minimum_improvements < 1:
        raise ValueError("minimum improvements must be positive")
    device = torch.device(args.device)
    parent_sha = file_sha256(args.parent_checkpoint)
    reranker_payload = torch.load(
        args.reranker_checkpoint, map_location="cpu", weights_only=False
    )
    if reranker_payload.get("schema") != REPORT_SCHEMA:
        raise ValueError("checkpoint is not a terminal action reranker")
    if reranker_payload.get("parent_checkpoint_sha256") != parent_sha:
        raise ValueError("reranker parent differs from evaluated policy")
    if reranker_payload.get("development_only") is not True:
        raise ValueError("reranker checkpoint lost its development-only marker")
    payload = torch.load(
        args.parent_checkpoint, map_location=device, weights_only=False
    )
    policy = _load_policy(payload, device)
    state = payload["model_state_dict"]
    card_features = torch.as_tensor(
        state["actor_encoder.card_stat_features"], device=device
    )
    semantic = state.get("actor_encoder.semantic_card_features")
    if semantic is not None:
        card_features = torch.cat(
            [card_features, torch.as_tensor(semantic, device=device)], dim=-1
        )
    splits = {
        "train": load_probe_examples(
            args.train_probes,
            checkpoint_sha256=parent_sha,
            model=policy,
            card_features=card_features,
            policy_device=device,
        ),
        "development": load_probe_examples(
            args.development_probes,
            checkpoint_sha256=parent_sha,
            model=policy,
            card_features=card_features,
            policy_device=device,
        ),
        "holdout": load_probe_examples(
            args.holdout_probes,
            checkpoint_sha256=parent_sha,
            model=policy,
            card_features=card_features,
            policy_device=device,
        ),
    }
    overlap = {
        "train_development": len(
            splits["train"].fingerprints & splits["development"].fingerprints
        ),
        "train_holdout": len(
            splits["train"].fingerprints & splits["holdout"].fingerprints
        ),
        "development_holdout": len(
            splits["development"].fingerprints & splits["holdout"].fingerprints
        ),
    }
    if any(overlap.values()):
        raise ValueError(f"terminal reranker split overlap: {overlap}")
    reranker = TerminalActionReranker(
        int(reranker_payload["state_feature_size"]),
        int(reranker_payload["action_feature_size"]),
        int(reranker_payload["rank"]),
    ).to(device)
    reranker.load_state_dict(reranker_payload["state_dict"], strict=True)
    if splits["holdout"].state_features.shape[-1] != reranker.state_size:
        raise ValueError("holdout state feature contract changed")
    if splits["holdout"].action_features.shape[-1] != reranker.action_size:
        raise ValueError("holdout action feature contract changed")
    metrics = evaluate_reranker(reranker, splits["holdout"], device=device)
    threshold = float(reranker_payload["override_probability_margin"])
    selected = fixed_threshold_row(metrics, threshold)
    root_details = fixed_threshold_root_details(
        reranker,
        splits["holdout"],
        device=device,
        threshold=threshold,
    )
    passed = bool(
        selected["worse_outcomes"] == 0
        and selected["improved_outcomes"] >= args.minimum_improvements
        and selected["correctable_roots"] >= args.minimum_improvements
    )
    report = {
        "schema": EVALUATION_SCHEMA,
        "status": "passed" if passed else "rejected",
        "parent_checkpoint": str(args.parent_checkpoint.resolve()),
        "parent_checkpoint_sha256": parent_sha,
        "reranker_checkpoint": str(args.reranker_checkpoint.resolve()),
        "reranker_checkpoint_sha256": file_sha256(args.reranker_checkpoint),
        "train_probes": str(args.train_probes.resolve()),
        "development_probes": str(args.development_probes.resolve()),
        "holdout_probes": str(args.holdout_probes.resolve()),
        "split_root_counts": {
            name: examples.roots for name, examples in splits.items()
        },
        "root_fingerprint_overlap": overlap,
        "frozen_rank": int(reranker_payload["rank"]),
        "frozen_override_probability_margin": threshold,
        "minimum_outcome_improvements": args.minimum_improvements,
        "metrics": metrics,
        "selected_threshold_metrics": selected,
        "root_details": root_details,
        "promotion_scope": (
            "offline architecture gate only; passing does not promote gameplay policy"
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
