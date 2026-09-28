#!/usr/bin/env python3
"""Finalize the fresh model-owned cumulative-hazard collapse screen."""

import argparse
import json
from pathlib import Path
from typing import Any


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _eval(path: Path) -> dict[str, float]:
    metrics = _object(path)["metrics"]
    return {
        "wins": float(metrics["wins"]),
        "losses": float(metrics["losses"]),
        "draws": float(metrics["draws"]),
        "crown_diff_per_game": float(metrics["crown_diff_per_game"]),
        "placement_rate": float(metrics["candidate_placement_rate"]),
        "noop_when_playable": float(metrics["candidate_noop_when_playable"]),
    }


def _human(path: Path) -> dict[str, float]:
    result = _object(path)["results"][0]
    return {
        "predicted_play_rate": float(result["predicted_play_rate"]),
        "expert_play_rate": float(result["expert_play_rate"]),
        "play_average_precision": float(result["play_average_precision"]),
        "play_roc_auc": float(result["play_roc_auc"]),
        "play_brier": float(result["play_brier"]),
        "play_ece_10_bin": float(result["play_ece_10_bin"]),
        "conditional_card_slot_accuracy": float(
            result["conditional_card_slot_accuracy"]
        ),
    }


def finalize(root: Path, output: Path) -> dict[str, Any]:
    parent = {
        "random": _eval(root / "parent" / "random12.metrics.json"),
        "balanced": _eval(root / "parent" / "balanced12.metrics.json"),
        "human": _human(root / "parent" / "human64.json"),
    }
    robustness = _object(root / "candidate" / "hand_robustness.json")["summary"]
    candidate = {
        "training_stable": _object(root / "training_stability.json").get("passes")
        is True,
        "random": _eval(root / "candidate" / "random12.metrics.json"),
        "balanced": _eval(root / "candidate" / "balanced12.metrics.json"),
        "direct_parent": _eval(root / "candidate" / "direct12.metrics.json"),
        "human": _human(root / "candidate" / "human64.json"),
        "hand_robustness": robustness,
    }
    reasons: list[str] = []
    if not candidate["training_stable"]:
        reasons.append("training_unstable")
    if candidate["random"]["wins"] < parent["random"]["wins"] + 2:
        reasons.append("random_win_gain_below_two")
    if candidate["balanced"]["wins"] < parent["balanced"]["wins"]:
        reasons.append("balanced_win_regression")
    if candidate["direct_parent"]["wins"] < 7:
        reasons.append("direct_parent_below_seven_wins")
    play_rate = candidate["human"]["predicted_play_rate"]
    if play_rate <= 0.005:
        reasons.append("deterministic_all_wait")
    if play_rate >= 0.20:
        reasons.append("deterministic_camera_overplay")
    if (
        candidate["human"]["play_average_precision"]
        < parent["human"]["play_average_precision"] + 0.002
    ):
        reasons.append("hazard_average_precision_gain_below_0.002")
    if float(robustness["card_and_tile_preservation_rate"]) < 0.999:
        reasons.append("hand_permutation_action_failure")
    if float(robustness["max_type_probability_equivariance_error"]) > 1e-5:
        reasons.append("hand_permutation_probability_failure")
    payload = {
        "schema": "clasher.fresh_f3_hazard_outcome_decision.v1",
        "parent": parent,
        "candidate": candidate,
        "rejection_reasons": reasons,
        "mixed_league_authorized": not reasons,
        "heldout_evaluation_authorized": False,
        "selected": "candidate" if not reasons else "parent",
        "gates": {
            "minimum_random_win_gain": 2,
            "minimum_direct_parent_wins": 7,
            "minimum_hazard_average_precision_gain": 0.002,
            "human_predicted_play_rate_interval": [0.005, 0.20],
            "minimum_hand_preservation": 0.999,
        },
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
    print(json.dumps(finalize(args.root, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
