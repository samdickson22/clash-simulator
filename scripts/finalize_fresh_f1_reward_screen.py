#!/usr/bin/env python3
"""Select a reward arm from development evidence or retain the parent."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ARMS = ("parent", "legacy", "gamma", "gamma_noleak")
CANDIDATES = ARMS[1:]


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strategy_summary(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("results")
    if not isinstance(results, dict) or set(results) != {
        "balanced",
        "bridge-pressure",
        "reactive-defense",
        "slow-push",
        "spell-control",
        "split-lane",
    }:
        raise ValueError("strategy benchmark has an unexpected opponent roster")
    wins = losses = draws = 0
    crowns = 0.0
    per_opponent: dict[str, dict[str, float]] = {}
    for name, raw in sorted(results.items()):
        if not isinstance(raw, dict) or int(raw.get("games", -1)) != 6:
            raise ValueError(f"strategy result {name!r} is not a six-game block")
        row = {
            "wins": float(raw["wins"]),
            "losses": float(raw["losses"]),
            "draws": float(raw["draws"]),
            "crown_diff": float(raw["crown_diff_per_game"]) * 6.0,
        }
        wins += int(row["wins"])
        losses += int(row["losses"])
        draws += int(row["draws"])
        crowns += row["crown_diff"]
        per_opponent[name] = row
    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "crown_diff": crowns,
        "per_opponent": per_opponent,
    }


def _eval_summary(payload: dict[str, Any], *, games: int) -> dict[str, float]:
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict) or int(metrics.get("games", -1)) != games:
        raise ValueError(f"expected a {games}-game evaluation")
    return {
        "wins": float(metrics["wins"]),
        "losses": float(metrics["losses"]),
        "draws": float(metrics["draws"]),
        "crown_diff": float(metrics["crown_diff_per_game"]) * games,
    }


def _human_summary(payload: dict[str, Any]) -> dict[str, float]:
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != 1:
        raise ValueError("human diagnostic must contain exactly one checkpoint")
    row = results[0]
    if not isinstance(row, dict):
        raise TypeError("invalid human diagnostic row")
    return {
        "predicted_play_rate": float(row["predicted_play_rate"]),
        "played_card_slot_accuracy": float(row["played_card_slot_accuracy"]),
        "conditional_card_slot_accuracy": float(row["conditional_card_slot_accuracy"]),
        "play_average_precision": float(row["play_average_precision"]),
    }


def finalize(
    root: Path, checkpoint_root: Path, parent: Path, output: Path
) -> dict[str, Any]:
    if not parent.is_file():
        raise FileNotFoundError(parent)
    summaries: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        arm_root = root / arm
        checkpoint = (
            parent
            if arm == "parent"
            else checkpoint_root / arm / "policy_v2_update_000020.pt"
        )
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        strategy = _strategy_summary(_object(arm_root / "strategy.json"))
        random = _eval_summary(_object(arm_root / "random12.metrics.json"), games=12)
        human = _human_summary(_object(arm_root / "human32.json"))
        if arm == "parent":
            stable = True
            direct = None
        else:
            stability = _object(root / arm / "training_stability.json")
            stable = stability.get("passes") is True
            direct = _eval_summary(
                _object(arm_root / "direct12.metrics.json"), games=12
            )
        summaries[arm] = {
            "checkpoint": str(checkpoint.resolve()),
            "checkpoint_sha256": _sha256(checkpoint),
            "training_stable": stable,
            "strategy": strategy,
            "random": random,
            "direct_parent": direct,
            "human": human,
        }

    parent_row = summaries["parent"]
    eligible: list[str] = []
    for arm in CANDIDATES:
        row = summaries[arm]
        reasons: list[str] = []
        if not row["training_stable"]:
            reasons.append("training_unstable")
        if row["strategy"]["wins"] < parent_row["strategy"]["wins"] + 2:
            reasons.append("strategy_win_gain_below_two")
        for name, baseline in parent_row["strategy"]["per_opponent"].items():
            if row["strategy"]["per_opponent"][name]["wins"] < baseline["wins"] - 1:
                reasons.append(f"strategy_regression:{name}")
        if row["random"]["wins"] < parent_row["random"]["wins"] - 1:
            reasons.append("random_regression")
        direct = row["direct_parent"]
        assert direct is not None
        if direct["wins"] < 7:
            reasons.append("direct_parent_below_7_wins")
        if (
            row["human"]["played_card_slot_accuracy"]
            < parent_row["human"]["played_card_slot_accuracy"] - 0.05
        ):
            reasons.append("human_card_regression")
        if (
            row["human"]["predicted_play_rate"]
            > parent_row["human"]["predicted_play_rate"] + 0.05
        ):
            reasons.append("human_overplay_regression")
        row["rejection_reasons"] = reasons
        if not reasons:
            eligible.append(arm)

    selected = "parent"
    if eligible:
        selected = max(
            eligible,
            key=lambda arm: (
                summaries[arm]["strategy"]["wins"]
                - summaries[arm]["strategy"]["losses"],
                summaries[arm]["strategy"]["crown_diff"],
                summaries[arm]["direct_parent"]["wins"],
            ),
        )
    payload = {
        "schema": "clasher.fresh_f1_reward_screen_decision.v1",
        "selected": selected,
        "candidate_promoted": selected != "parent",
        "heldout_evaluation_authorized": selected != "parent",
        "summaries": summaries,
        "selection_contract": {
            "strategy_win_gain": 2,
            "maximum_per_strategy_win_regression": 1,
            "maximum_random_win_regression": 1,
            "minimum_direct_parent_wins": 7,
            "maximum_human_card_accuracy_regression": 0.05,
            "maximum_human_play_rate_increase": 0.05,
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
    parser.add_argument("--checkpoint-root", required=True, type=Path)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            finalize(args.root, args.checkpoint_root, args.parent, args.output),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
