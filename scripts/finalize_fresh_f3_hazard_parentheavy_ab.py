#!/usr/bin/env python3
"""Select or reject parent-heavy repair arms from matched development evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ARMS = ("anchor", "plain", "kl005")


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(*, root: Path, output: Path) -> dict[str, Any]:
    human_results = _object(root / "human64.json")["results"]
    if not isinstance(human_results, list) or len(human_results) != 3:
        raise ValueError("human screen must contain anchor, plain, and KL arms")
    rows: dict[str, dict[str, Any]] = {}
    evidence = [root / "human64.json"]
    for arm, human in zip(ARMS, human_results, strict=True):
        strategy_path = root / arm / "strategy.json"
        direct_path = root / arm / "direct24.metrics.json"
        random_path = root / arm / "random24.metrics.json"
        hog_path = root / arm / "hog12.metrics.json"
        strategy = _object(strategy_path)["results"]
        direct = _object(direct_path)["metrics"]
        random = _object(random_path)["metrics"]
        hog = _object(hog_path)["metrics"]
        row: dict[str, Any] = {
            "checkpoint": str(human["checkpoint"]),
            "checkpoint_sha256": str(human["checkpoint_sha256"]),
            "direct": {
                "wins": float(direct["wins"]),
                "losses": float(direct["losses"]),
                "wins_as_player0": float(direct["wins_as_player0"]),
                "wins_as_player1": float(direct["wins_as_player1"]),
                "crown_difference": float(direct["crown_diff_per_game"]) * 24,
                "noop_when_playable": float(direct["candidate_noop_when_playable"]),
            },
            "strategy": {
                "wins": sum(float(result["wins"]) for result in strategy.values()),
                "losses": sum(float(result["losses"]) for result in strategy.values()),
                "per_opponent": {
                    name: {
                        "wins": float(result["wins"]),
                        "losses": float(result["losses"]),
                    }
                    for name, result in strategy.items()
                },
            },
            "random": {"wins": float(random["wins"]), "losses": float(random["losses"])},
            "hog": {"wins": float(hog["wins"]), "losses": float(hog["losses"])},
            "human": {
                name: float(human[name])
                for name in (
                    "predicted_play_rate",
                    "play_average_precision",
                    "play_roc_auc",
                    "play_brier",
                    "play_ece_10_bin",
                    "conditional_card_slot_accuracy",
                )
            },
        }
        rows[arm] = row
        evidence.extend((strategy_path, direct_path, random_path, hog_path))

    baseline = rows["anchor"]
    for arm in ("plain", "kl005"):
        row = rows[arm]
        reasons: list[str] = []
        if row["direct"]["wins"] < baseline["direct"]["wins"] + 2:
            reasons.append("direct_gain_below_two")
        if min(row["direct"]["wins_as_player0"], row["direct"]["wins_as_player1"]) < 6:
            reasons.append("direct_seat_below_six")
        if row["direct"]["noop_when_playable"] >= 0.95:
            reasons.append("playable_noop_at_or_above_95_percent")
        if row["strategy"]["wins"] < baseline["strategy"]["wins"] + 2:
            reasons.append("strategy_gain_below_two")
        for name, before in baseline["strategy"]["per_opponent"].items():
            if row["strategy"]["per_opponent"][name]["wins"] < before["wins"] - 1:
                reasons.append(f"strategy_regression:{name}")
        if row["random"]["wins"] < baseline["random"]["wins"] - 1:
            reasons.append("random_regression")
        if row["hog"]["wins"] < baseline["hog"]["wins"]:
            reasons.append("hog_regression")
        if row["human"]["play_average_precision"] < baseline["human"]["play_average_precision"] - 0.002:
            reasons.append("human_hazard_ap_regression")
        if row["human"]["conditional_card_slot_accuracy"] < baseline["human"]["conditional_card_slot_accuracy"] - 0.01:
            reasons.append("human_card_accuracy_regression")
        row["rejection_reasons"] = reasons

    rows["anchor"]["rejection_reasons"] = []
    eligible = [arm for arm in ("plain", "kl005") if not rows[arm]["rejection_reasons"]]
    selected = max(
        eligible,
        key=lambda arm: (
            rows[arm]["direct"]["wins"],
            rows[arm]["strategy"]["wins"],
            rows[arm]["random"]["wins"],
        ),
    ) if eligible else "anchor"
    confirmation = (
        rows["plain"]["rejection_reasons"] == ["random_regression"]
        and "plain" not in eligible
    )
    payload = {
        "schema": "clasher.fresh_f3_hazard_parentheavy_ab.v1",
        "arms": rows,
        "selected": selected,
        "random_confirmation_authorized": confirmation,
        "external_evaluation_authorized": bool(eligible),
        "promotion_authorized": False,
        "evidence_sha256": {str(path.resolve()): _sha256(path) for path in evidence},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(finalize(root=args.root, output=args.output), sort_keys=True))


if __name__ == "__main__":
    main()
