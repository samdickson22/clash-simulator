#!/usr/bin/env python3
"""Finalize the second-seed legacy reward replication without held-out data."""

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


def finalize(first_decision: Path, root: Path, output: Path) -> dict[str, object]:
    first = _object(first_decision)
    first_rows = first["summaries"]
    parent: dict[str, Any] = {
        "strategy": _strategy_summary(_object(root / "parent" / "strategy.json")),
        "random": _eval_summary(
            _object(root / "parent" / "random12.metrics.json"), games=12
        ),
        "human": _human_summary(_object(root / "parent" / "human32.json")),
    }
    candidate: dict[str, Any] = {
        "strategy": _strategy_summary(_object(root / "candidate" / "strategy.json")),
        "random": _eval_summary(
            _object(root / "candidate" / "random12.metrics.json"), games=12
        ),
        "direct_parent": _eval_summary(
            _object(root / "candidate" / "direct12.metrics.json"), games=12
        ),
        "human": _human_summary(_object(root / "candidate" / "human32.json")),
        "training_stable": _object(root / "training_stability.json").get("passes")
        is True,
    }
    first_gain = int(first_rows["legacy"]["strategy"]["wins"]) - int(
        first_rows["parent"]["strategy"]["wins"]
    )
    second_gain = int(candidate["strategy"]["wins"]) - int(parent["strategy"]["wins"])
    reasons: list[str] = []
    if not candidate["training_stable"]:
        reasons.append("training_unstable")
    if first_gain + second_gain < 4:
        reasons.append("combined_strategy_win_gain_below_four")
    for name, baseline in parent["strategy"]["per_opponent"].items():
        if candidate["strategy"]["per_opponent"][name]["wins"] < baseline["wins"] - 1:
            reasons.append(f"second_seed_strategy_regression:{name}")
    if candidate["random"]["wins"] < parent["random"]["wins"] - 1:
        reasons.append("second_seed_random_regression")
    if candidate["direct_parent"]["wins"] < 7:
        reasons.append("second_seed_direct_parent_below_7_wins")
    if (
        candidate["human"]["played_card_slot_accuracy"]
        < parent["human"]["played_card_slot_accuracy"] - 0.05
    ):
        reasons.append("second_seed_human_card_regression")
    if (
        candidate["human"]["predicted_play_rate"]
        > parent["human"]["predicted_play_rate"] + 0.05
    ):
        reasons.append("second_seed_human_overplay_regression")
    payload: dict[str, object] = {
        "schema": "clasher.fresh_f1_legacy_replication_decision.v1",
        "first_seed_strategy_win_gain": first_gain,
        "second_seed_strategy_win_gain": second_gain,
        "combined_strategy_win_gain": first_gain + second_gain,
        "parent": parent,
        "candidate": candidate,
        "rejection_reasons": reasons,
        "heldout_evaluation_authorized": not reasons,
        "selected": "candidate" if not reasons else "parent",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-decision", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            finalize(args.first_decision, args.root, args.output), sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
