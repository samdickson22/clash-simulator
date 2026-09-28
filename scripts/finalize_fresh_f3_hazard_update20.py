#!/usr/bin/env python3
"""Decide whether full-weight hazard update 20 earns mixed-league PPO."""

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.finalize_fresh_f1_reward_screen import (
    _eval_summary,
    _object,
    _strategy_summary,
)


def _human(path: Path) -> dict[str, float]:
    result = _object(path)["results"][0]
    return {
        "predicted_play_rate": float(result["predicted_play_rate"]),
        "play_average_precision": float(result["play_average_precision"]),
        "play_roc_auc": float(result["play_roc_auc"]),
        "play_brier": float(result["play_brier"]),
        "play_ece_10_bin": float(result["play_ece_10_bin"]),
        "conditional_card_slot_accuracy": float(
            result["conditional_card_slot_accuracy"]
        ),
    }


def finalize(root: Path, stability: Path, output: Path) -> dict[str, Any]:
    parent: dict[str, Any] = {
        "strategy": _strategy_summary(_object(root / "parent" / "strategy.json")),
        "random": _eval_summary(
            _object(root / "parent" / "random24.metrics.json"), games=24
        ),
        "human": _human(root / "parent" / "human64.json"),
    }
    candidate: dict[str, Any] = {
        "strategy": _strategy_summary(_object(root / "candidate" / "strategy.json")),
        "random": _eval_summary(
            _object(root / "candidate" / "random24.metrics.json"), games=24
        ),
        "direct_parent": _eval_summary(
            _object(root / "candidate" / "direct24.metrics.json"), games=24
        ),
        "human": _human(root / "candidate" / "human64.json"),
        "training_stable": _object(stability).get("passes") is True,
    }
    robustness = _object(root / "candidate" / "hand_robustness.json")["summary"]
    candidate["hand_robustness"] = robustness
    reasons: list[str] = []
    if not candidate["training_stable"]:
        reasons.append("training_unstable")
    if candidate["random"]["wins"] < parent["random"]["wins"] + 4:
        reasons.append("random_win_gain_below_four")
    if candidate["direct_parent"]["wins"] < 14:
        reasons.append("direct_parent_below_14_wins")
    if candidate["strategy"]["wins"] < parent["strategy"]["wins"]:
        reasons.append("strategy_total_regression")
    for name, baseline in parent["strategy"]["per_opponent"].items():
        if candidate["strategy"]["per_opponent"][name]["wins"] < baseline["wins"] - 1:
            reasons.append(f"strategy_regression:{name}")
    play_rate = candidate["human"]["predicted_play_rate"]
    if not 0.005 < play_rate < 0.20:
        reasons.append("human_play_rate_outside_interval")
    if (
        candidate["human"]["play_average_precision"]
        < parent["human"]["play_average_precision"] - 0.002
    ):
        reasons.append("hazard_average_precision_regression")
    if (
        candidate["human"]["conditional_card_slot_accuracy"]
        < parent["human"]["conditional_card_slot_accuracy"] - 0.01
    ):
        reasons.append("human_card_accuracy_regression")
    if float(robustness["card_and_tile_preservation_rate"]) < 0.999:
        reasons.append("hand_permutation_action_failure")
    if float(robustness["max_type_probability_equivariance_error"]) > 1e-5:
        reasons.append("hand_permutation_probability_failure")
    payload = {
        "schema": "clasher.fresh_f3_hazard_update20_decision.v1",
        "parent": parent,
        "candidate": candidate,
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
    parser.add_argument("--stability", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(finalize(args.root, args.stability, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
