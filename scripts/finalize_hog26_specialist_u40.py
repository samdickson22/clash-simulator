#!/usr/bin/env python3
"""Record the update-40 specialist decision from matched development evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(*, root: Path, stability_path: Path, output: Path) -> dict[str, Any]:
    evidence: list[Path] = [stability_path]
    arms: dict[str, dict[str, Any]] = {}
    human = _object(root / "u40" / "human128.json")["results"]
    hoglike_path = root / "u40" / "human_hoglike10.json"
    hoglike = _object(hoglike_path)["results"]
    if len(human) != 2:
        raise ValueError("human comparison must contain parent and update 40")
    human_by_sha = {str(row["checkpoint_sha256"]): row for row in human}
    hoglike_by_sha = {str(row["checkpoint_sha256"]): row for row in hoglike}
    for arm in ("parent", "u40"):
        random_path = root / arm / "random24.metrics.json"
        direct_path = root / arm / "direct24.metrics.json"
        strategy_path = root / arm / "strategy.json"
        utilization_path = root / arm / "utilization.json"
        evidence.extend((random_path, direct_path, strategy_path, utilization_path))
        random_payload = _object(random_path)
        direct_payload = _object(direct_path)
        strategy = _object(strategy_path)["results"]
        utilization = _object(utilization_path)
        checkpoint_sha = str(random_payload["checkpoint_sha256"])
        row_human = human_by_sha[checkpoint_sha]
        row_hoglike = hoglike_by_sha[checkpoint_sha]
        arms[arm] = {
            "checkpoint": random_payload["checkpoint"],
            "checkpoint_sha256": checkpoint_sha,
            "random": random_payload["metrics"],
            "direct": direct_payload["metrics"],
            "strategy": {
                "wins": sum(float(row["wins"]) for row in strategy.values()),
                "losses": sum(float(row["losses"]) for row in strategy.values()),
                "per_opponent": {
                    name: {"wins": float(row["wins"]), "losses": float(row["losses"])}
                    for name, row in strategy.items()
                },
            },
            "utilization": {
                key: utilization[key]
                for key in (
                    "plays",
                    "zero_use_games",
                    "zero_use_rate",
                    "window_conversion_rate",
                    "gate",
                )
            },
            "human": {
                key: float(row_human[key])
                for key in (
                    "predicted_play_rate",
                    "play_average_precision",
                    "play_roc_auc",
                    "play_brier",
                    "conditional_card_slot_accuracy",
                )
            },
            "human_hoglike": {
                key: float(row_hoglike[key])
                for key in (
                    "play_average_precision",
                    "play_roc_auc",
                    "play_brier",
                    "conditional_card_slot_accuracy",
                )
            },
        }
    evidence.append(root / "u40" / "human128.json")
    evidence.append(hoglike_path)

    parent = arms["parent"]
    candidate = arms["u40"]
    gameplay_reasons: list[str] = []
    if candidate["random"]["wins"] < parent["random"]["wins"] - 1:
        gameplay_reasons.append("random_regression")
    if candidate["direct"]["wins"] < parent["direct"]["wins"] + 2:
        gameplay_reasons.append("direct_gain_below_two")
    if candidate["strategy"]["wins"] < parent["strategy"]["wins"] + 1:
        gameplay_reasons.append("strategy_gain_below_one")
    for name, before in parent["strategy"]["per_opponent"].items():
        if candidate["strategy"]["per_opponent"][name]["wins"] < before["wins"] - 1:
            gameplay_reasons.append(f"strategy_regression:{name}")
    for workload in ("random", "direct"):
        if candidate[workload]["candidate_noop_when_playable"] >= 0.95:
            gameplay_reasons.append(f"playable_noop:{workload}")
    if candidate["utilization"]["gate"]["passed"] is not True:
        gameplay_reasons.append("hog_utilization_gate")
    if candidate["human"]["play_average_precision"] < parent["human"]["play_average_precision"] - 0.002:
        gameplay_reasons.append("human_timing_ap_regression")

    unresolved = []
    if candidate["human"]["conditional_card_slot_accuracy"] < parent["human"]["conditional_card_slot_accuracy"] - 0.01:
        unresolved.append("all_deck_human_card_accuracy_regression")
    if candidate["human_hoglike"]["conditional_card_slot_accuracy"] < parent["human_hoglike"]["conditional_card_slot_accuracy"] - 0.02:
        unresolved.append("hoglike_human_card_accuracy_regression")
    development_selected = not gameplay_reasons
    payload = {
        "schema": "clasher.hog26_specialist_u40_decision.v1",
        "arms": arms,
        "selected": "u40" if development_selected else "parent",
        "gameplay_rejection_reasons": gameplay_reasons,
        "unresolved_promotion_blockers": unresolved,
        "card_rehearsal_repair_authorized": development_selected and bool(unresolved),
        "competent_play_proven": False,
        "expand_learner_decks_authorized": False,
        "fresh_quarantine_evaluation_authorized": False,
        "promotion_authorized": False,
        "evidence_sha256": {str(path.resolve()): _sha(path) for path in evidence},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--stability", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(finalize(root=args.root, stability_path=args.stability, output=args.output), sort_keys=True))


if __name__ == "__main__":
    main()
