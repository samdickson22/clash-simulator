#!/usr/bin/env python3
"""Finalize the first unseen-deck/archetype gate for hazard update 30."""

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.finalize_fresh_f1_reward_screen import (
    _eval_summary,
    _object,
)

STRATEGY_OPPONENTS = {
    "balanced",
    "bridge-pressure",
    "reactive-defense",
    "slow-push",
    "spell-control",
    "split-lane",
}


def _heldout_strategy_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize the predeclared four-game held-out strategy blocks."""
    protocol = payload.get("protocol")
    results = payload.get("results")
    if not isinstance(protocol, dict) or int(protocol.get("games_per_opponent", -1)) != 4:
        raise ValueError("held-out strategy protocol is not four games per opponent")
    if not isinstance(results, dict) or set(results) != STRATEGY_OPPONENTS:
        raise ValueError("held-out strategy benchmark has an unexpected opponent roster")
    wins = losses = draws = 0
    crowns = 0.0
    per_opponent: dict[str, dict[str, float]] = {}
    for name, raw in sorted(results.items()):
        if not isinstance(raw, dict) or int(raw.get("games", -1)) != 4:
            raise ValueError(f"held-out strategy result {name!r} is not a four-game block")
        row = {
            "wins": float(raw["wins"]),
            "losses": float(raw["losses"]),
            "draws": float(raw["draws"]),
            "crown_diff": float(raw["crown_diff_per_game"]) * 4.0,
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


def finalize(root: Path, output: Path) -> dict[str, Any]:
    parent = {
        "strategy": _heldout_strategy_summary(
            _object(root / "parent" / "strategy.json")
        ),
        "random": _eval_summary(
            _object(root / "parent" / "random24.metrics.json"), games=24
        ),
    }
    direct_payload = _object(root / "candidate" / "direct48.metrics.json")
    direct_metrics = direct_payload["metrics"]
    candidate: dict[str, Any] = {
        "strategy": _heldout_strategy_summary(
            _object(root / "candidate" / "strategy.json")
        ),
        "random": _eval_summary(
            _object(root / "candidate" / "random24.metrics.json"), games=24
        ),
        "direct_parent": _eval_summary(direct_payload, games=48),
        "direct_wins_as_player0": float(direct_metrics["wins_as_player0"]),
        "direct_wins_as_player1": float(direct_metrics["wins_as_player1"]),
    }
    reasons: list[str] = []
    if candidate["random"]["wins"] < parent["random"]["wins"] - 1:
        reasons.append("heldout_random_regression")
    if candidate["strategy"]["wins"] < parent["strategy"]["wins"]:
        reasons.append("heldout_strategy_total_regression")
    for name, baseline in parent["strategy"]["per_opponent"].items():
        if candidate["strategy"]["per_opponent"][name]["wins"] < baseline["wins"] - 1:
            reasons.append(f"heldout_strategy_regression:{name}")
    if candidate["direct_parent"]["wins"] < 27:
        reasons.append("heldout_direct_below_27_wins")
    if (
        candidate["direct_wins_as_player0"] < 12
        or candidate["direct_wins_as_player1"] < 12
    ):
        reasons.append("heldout_direct_losing_seat")
    payload = {
        "schema": "clasher.fresh_f3_hazard_heldout_development.v1",
        "parent": parent,
        "candidate": candidate,
        "rejection_reasons": reasons,
        "expanded_safety_evaluation_authorized": not reasons,
        "promotion_authorized": False,
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
