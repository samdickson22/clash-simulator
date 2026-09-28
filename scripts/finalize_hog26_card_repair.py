#!/usr/bin/env python3
"""Select or reject the leakage-safe card-rehearsal repair checkpoint."""

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


def _human_row(path: Path, update: int) -> dict[str, Any]:
    rows = _object(path)["results"]
    matches = [row for row in rows if int(row["checkpoint_update"]) == update]
    if len(matches) != 1:
        raise ValueError(f"expected one human row for update {update}")
    row = matches[0]
    if not isinstance(row, dict):
        raise TypeError("human result row must be an object")
    return row


def finalize(*, baseline_root: Path, candidate_root: Path, gate_root: Path, output: Path) -> dict[str, Any]:
    evidence: list[Path] = []
    arms: dict[str, dict[str, Any]] = {}
    for arm, root, update in (
        ("u40", baseline_root, 40),
        ("u46", candidate_root, 46),
    ):
        paths = {
            "random": root / "random24.metrics.json",
            "direct": root / "direct24.metrics.json",
            "strategy": root / "strategy.json",
            "utilization": root / "utilization.json",
        }
        evidence.extend(paths.values())
        strategy = _object(paths["strategy"])["results"]
        human = _human_row(gate_root / "human128.json", update)
        hoglike = _human_row(gate_root / "human_hoglike10.json", update)
        arms[arm] = {
            "checkpoint": _object(paths["random"])["checkpoint"],
            "checkpoint_sha256": _object(paths["random"])["checkpoint_sha256"],
            "random": _object(paths["random"])["metrics"],
            "direct": _object(paths["direct"])["metrics"],
            "strategy": {
                "wins": sum(float(row["wins"]) for row in strategy.values()),
                "losses": sum(float(row["losses"]) for row in strategy.values()),
                "per_opponent": {
                    name: {"wins": float(row["wins"]), "losses": float(row["losses"])}
                    for name, row in strategy.items()
                },
            },
            "utilization": _object(paths["utilization"]),
            "human": human,
            "human_hoglike": hoglike,
        }
    evidence.extend((gate_root / "human128.json", gate_root / "human_hoglike10.json"))
    before, after = arms["u40"], arms["u46"]
    reasons: list[str] = []
    if after["random"]["wins"] < before["random"]["wins"] - 1:
        reasons.append("random_regression")
    if after["direct"]["wins"] < before["direct"]["wins"] - 1:
        reasons.append("direct_regression")
    if after["strategy"]["wins"] < before["strategy"]["wins"] - 1:
        reasons.append("strategy_regression")
    for name, row in before["strategy"]["per_opponent"].items():
        if after["strategy"]["per_opponent"][name]["wins"] < row["wins"] - 1:
            reasons.append(f"strategy_regression:{name}")
    if after["utilization"]["gate"]["passed"] is not True:
        reasons.append("hog_utilization_gate")
    if after["human"]["conditional_card_slot_accuracy"] < before["human"]["conditional_card_slot_accuracy"] + 0.05:
        reasons.append("all_deck_card_repair_below_five_points")
    if after["human_hoglike"]["conditional_card_slot_accuracy"] < before["human_hoglike"]["conditional_card_slot_accuracy"] + 0.10:
        reasons.append("hoglike_card_repair_below_ten_points")
    if after["human_hoglike"]["play_average_precision"] < before["human_hoglike"]["play_average_precision"] - 0.002:
        reasons.append("hoglike_timing_ap_regression")
    selected = "u46" if not reasons else "u40"
    strategy_wins = int(arms[selected]["strategy"]["wins"])
    random_wins = int(arms[selected]["random"]["wins"])
    competent = strategy_wins >= 12 and random_wins >= 12
    payload = {
        "schema": "clasher.hog26_card_rehearsal_repair_decision.v1",
        "arms": arms,
        "selected": selected,
        "rejection_reasons": reasons,
        "strategy_pfsp_continuation_authorized": selected == "u46" and not competent,
        "competent_play_proven": competent,
        "expand_learner_decks_authorized": competent,
        "fresh_quarantine_evaluation_authorized": False,
        "promotion_authorized": False,
        "evidence_sha256": {str(path.resolve()): _sha(path) for path in evidence},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--gate-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(finalize(baseline_root=args.baseline_root, candidate_root=args.candidate_root, gate_root=args.gate_root, output=args.output), sort_keys=True))


if __name__ == "__main__":
    main()
