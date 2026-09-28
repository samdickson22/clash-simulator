#!/usr/bin/env python3
"""Resolve the sole update-20 blocker on an exact disjoint complement."""

import argparse
import json
from pathlib import Path
from typing import Any


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _human_result(path: Path) -> dict[str, Any]:
    result = _object(path)["results"][0]
    if not isinstance(result, dict):
        raise TypeError(f"expected result object: {path}")
    return result


def confirm(root: Path, output: Path) -> dict[str, Any]:
    initial = _object(root / "decision.json")
    if initial.get("rejection_reasons") != ["human_card_accuracy_regression"]:
        raise ValueError("confirmation requires exactly the card-accuracy blocker")
    complement = _object(root / "human52_complement.json")
    if (
        complement.get("exclude_max_episodes") != 64
        or complement.get("exclude_episode_seed") != 1068604
        or complement.get("evaluated_episodes") != 299
    ):
        raise ValueError("confirmation corpus is not the exact disjoint complement")
    complement_results = complement["results"]
    if [result["checkpoint_update"] for result in complement_results] != [10, 20]:
        raise ValueError("confirmation checkpoint order differs")
    development_parent = _human_result(root / "parent" / "human64.json")
    development_candidate = _human_result(root / "candidate" / "human64.json")
    complement_parent, complement_candidate = complement_results

    def correct(result: dict[str, Any]) -> float:
        return float(result["conditional_card_slot_accuracy"]) * float(
            result["play_samples"]
        )

    total_plays = int(development_parent["play_samples"]) + int(
        complement_parent["play_samples"]
    )
    if total_plays != 1411:
        raise ValueError("development plus complement does not cover all play labels")
    combined_parent = (
        correct(development_parent) + correct(complement_parent)
    ) / total_plays
    combined_candidate = (
        correct(development_candidate) + correct(complement_candidate)
    ) / total_plays
    complement_card_delta = float(
        complement_candidate["conditional_card_slot_accuracy"]
    ) - float(complement_parent["conditional_card_slot_accuracy"])
    combined_card_delta = combined_candidate - combined_parent
    reasons: list[str] = []
    if complement_card_delta < -0.01:
        reasons.append("complement_card_accuracy_regression")
    if combined_card_delta < -0.01:
        reasons.append("combined_card_accuracy_regression")
    if float(complement_candidate["play_average_precision"]) < float(
        complement_parent["play_average_precision"]
    ):
        reasons.append("complement_hazard_ap_regression")
    payload = {
        "schema": "clasher.fresh_f3_hazard_update20_confirmation.v1",
        "initial_decision": str((root / "decision.json").resolve()),
        "development_segments": 64,
        "complement_segments": 299,
        "combined_segments": 363,
        "combined_play_samples": total_plays,
        "development_card_accuracy": {
            "parent": float(development_parent["conditional_card_slot_accuracy"]),
            "candidate": float(
                development_candidate["conditional_card_slot_accuracy"]
            ),
        },
        "complement_card_accuracy": {
            "parent": float(complement_parent["conditional_card_slot_accuracy"]),
            "candidate": float(
                complement_candidate["conditional_card_slot_accuracy"]
            ),
            "delta": complement_card_delta,
        },
        "combined_card_accuracy": {
            "parent": combined_parent,
            "candidate": combined_candidate,
            "delta": combined_card_delta,
        },
        "complement_hazard": {
            "parent_ap": float(complement_parent["play_average_precision"]),
            "candidate_ap": float(complement_candidate["play_average_precision"]),
            "parent_roc_auc": float(complement_parent["play_roc_auc"]),
            "candidate_roc_auc": float(complement_candidate["play_roc_auc"]),
        },
        "rejection_reasons": reasons,
        "mixed_league_authorized": not reasons,
        "heldout_evaluation_authorized": False,
        "selected": "candidate" if not reasons else "parent",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(confirm(args.root, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
