#!/usr/bin/env python3
"""Select or reject a causal-cadence rehearsal coefficient from fixed gates."""

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
    arms: dict[str, dict[str, Any]] = {}
    for arm in ("0010", "0025"):
        report_root = Path(f"reports/fresh_f3_causal_rehearsal_{arm}_seed1067901")
        candidate: dict[str, Any] = {
            "coefficient": {"0010": 0.01, "0025": 0.025}[arm],
            "training_stable": _object(report_root / "training_stability.json").get(
                "passes"
            )
            is True,
            "random": _eval(root / arm / "random12.metrics.json"),
            "balanced": _eval(root / arm / "balanced12.metrics.json"),
            "human": _human(root / arm / "human64.json"),
        }
        reasons: list[str] = []
        if not candidate["training_stable"]:
            reasons.append("training_unstable")
        if candidate["random"]["wins"] < parent["random"]["wins"] + 2:
            reasons.append("random_win_gain_below_two")
        if candidate["balanced"]["wins"] < parent["balanced"]["wins"]:
            reasons.append("balanced_win_regression")
        play_rate = candidate["human"]["predicted_play_rate"]
        if play_rate <= 0.005:
            reasons.append("deterministic_all_wait")
        if play_rate >= 0.5:
            reasons.append("deterministic_camera_overplay")
        if (
            candidate["human"]["play_average_precision"]
            < parent["human"]["play_average_precision"]
        ):
            reasons.append("human_play_average_precision_regression")
        candidate["rejection_reasons"] = reasons
        arms[arm] = candidate

    viable = [name for name, arm in arms.items() if not arm["rejection_reasons"]]
    selected = "parent"
    if viable:
        selected = max(
            viable,
            key=lambda name: (
                arms[name]["random"]["wins"] + arms[name]["balanced"]["wins"],
                arms[name]["human"]["play_average_precision"],
                -arms[name]["human"]["play_ece_10_bin"],
                -arms[name]["coefficient"],
            ),
        )
    payload = {
        "schema": "clasher.fresh_f3_causal_rehearsal_screen.v1",
        "parent": parent,
        "arms": arms,
        "selected": selected,
        "mixed_league_authorized": selected != "parent",
        "heldout_evaluation_authorized": False,
        "gates": {
            "minimum_random_win_gain": 2,
            "minimum_human_predicted_play_rate": 0.005,
            "maximum_human_predicted_play_rate": 0.5,
            "require_no_balanced_win_regression": True,
            "require_no_human_play_ap_regression": True,
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
