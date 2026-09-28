#!/usr/bin/env python3
"""Finalize the bounded fresh-F3 random-opponent outcome pilot."""

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.finalize_fresh_f1_reward_screen import (
    _eval_summary,
    _human_summary,
    _object,
    _strategy_summary,
)


def finalize(root: Path, output: Path) -> dict[str, Any]:
    parent: dict[str, Any] = {
        "strategy": _strategy_summary(_object(root / "parent" / "strategy.json")),
        "random": _eval_summary(
            _object(root / "parent" / "random24.metrics.json"), games=24
        ),
        "human": _human_summary(_object(root / "parent" / "human64.json")),
    }
    candidate: dict[str, Any] = {
        "strategy": _strategy_summary(_object(root / "candidate" / "strategy.json")),
        "random": _eval_summary(
            _object(root / "candidate" / "random24.metrics.json"), games=24
        ),
        "direct_parent": _eval_summary(
            _object(root / "candidate" / "direct24.metrics.json"), games=24
        ),
        "human": _human_summary(_object(root / "candidate" / "human64.json")),
        "training_stable": _object(root / "training_stability.json").get("passes")
        is True,
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
    play_rate = float(candidate["human"]["predicted_play_rate"])
    if play_rate <= 0.001:
        reasons.append("deterministic_all_wait")
    if play_rate >= 0.5:
        reasons.append("deterministic_camera_overplay")
    if float(robustness["card_and_tile_preservation_rate"]) < 0.999:
        reasons.append("hand_permutation_action_failure")
    if float(robustness["max_type_probability_equivariance_error"]) > 1e-5:
        reasons.append("hand_permutation_probability_failure")
    payload: dict[str, Any] = {
        "schema": "clasher.fresh_f3_random_outcome_decision.v1",
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
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(finalize(args.root, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
