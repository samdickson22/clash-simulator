from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def evaluate_probe(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("schema") != "clasher.public_structured_action_value_fit.v2":
        raise ValueError("unsupported structured action-value fit report")
    split = dict(report["validation_split_contract"])
    if split.get("schema") != (
        "clasher.game_disjoint_selection_calibration_holdout.v1"
    ):
        raise ValueError("structured probe lacks a three-way validation contract")
    if int(split.get("seed", -1)) != 1169102:
        raise ValueError("structured validation partition seed changed")
    game_sets = {
        name: {int(value) for value in split["games"][name]}
        for name in ("selection", "calibration", "holdout")
    }
    if any(not values for values in game_sets.values()):
        raise ValueError("structured probe contains an empty validation partition")
    if (
        game_sets["selection"] & game_sets["calibration"]
        or game_sets["selection"] & game_sets["holdout"]
        or game_sets["calibration"] & game_sets["holdout"]
    ):
        raise ValueError("structured validation partitions overlap by game")
    expected_game_counts = {"selection": 30, "calibration": 30, "holdout": 40}
    actual_game_counts = {name: len(values) for name, values in game_sets.items()}
    if actual_game_counts != expected_game_counts:
        raise ValueError("structured validation game partition counts changed")
    state_counts = {
        name: int(split["states"][name])
        for name in ("selection", "calibration", "holdout")
    }
    for name in ("selection", "calibration", "validation"):
        split_name = "holdout" if name == "validation" else name
        if int(report[name]["states"]) != state_counts[split_name]:
            raise ValueError(f"structured {split_name} state count changed")
    validation = dict(report["validation"])
    selected_threshold = float(report["minimum_score_gain"])
    selected_rows = [
        row
        for row in report["calibration_sweep"]
        if float(row["threshold"]) == selected_threshold
    ]
    if len(selected_rows) != 1:
        raise ValueError("structured calibration threshold is not unique")
    selected = dict(selected_rows[0])
    calibration_regressions = sum(
        int(value) for value in selected["regressions"].values()
    )
    holdout = dict(report["holdout_threshold_metrics"])
    if float(holdout["threshold"]) != selected_threshold:
        raise ValueError("holdout metrics use a different controller threshold")
    if int(holdout["states"]) != state_counts["holdout"]:
        raise ValueError("holdout threshold metrics use different states")
    holdout_regressions = sum(
        int(value) for value in holdout["regressions"].values()
    )
    holdout_improvements = sum(
        int(value) for value in holdout["improvements"].values()
    )
    bootstrap = dict(report["holdout_cluster_bootstrap"])
    if (
        bootstrap.get("schema") != "clasher.game_cluster_bootstrap.v1"
        or int(bootstrap.get("seed", -1)) != 1169103
        or int(bootstrap.get("samples", 0)) != 10_000
        or int(bootstrap.get("games", 0)) != 40
        or int(bootstrap.get("accuracy_games", 0)) != 40
        or int(bootstrap.get("optimal_action_rate_games", 0)) != 40
        or int(bootstrap.get("outcome_accuracy_games", 0)) < 20
    ):
        raise ValueError("structured holdout cluster bootstrap contract changed")
    gates = {
        "overall_pairwise_accuracy": float(validation["accuracy"]) >= 0.62,
        "outcome_pairwise_accuracy": float(validation["outcome_accuracy"]) >= 0.67,
        "optimal_action_rate": float(validation["optimal_action_rate"])
        > 0.41990950226244345,
        "minimum_safe_overrides": int(holdout["overrides"]) >= 25,
        "minimum_safe_improvements": holdout_improvements >= 15,
        "zero_calibration_regressions": calibration_regressions == 0,
        "zero_holdout_regressions": holdout_regressions == 0,
        "overall_cluster_lower_above_pooled": float(
            bootstrap["accuracy_ci95"][0]
        )
        > 0.5965095557057702,
        "outcome_cluster_lower_above_pooled": float(
            bootstrap["outcome_accuracy_ci95"][0]
        )
        > 0.6279212792127922,
        "optimal_cluster_lower_above_pooled": float(
            bootstrap["optimal_action_rate_ci95"][0]
        )
        > 0.41990950226244345,
    }
    return {
        "schema": "clasher.hog26_structured_action_value_probe_decision.v1",
        "passed": all(gates.values()),
        "representation_probe_passed": all(gates.values()),
        "promotion_authorized": False,
        "phase_balanced_followup_required": all(gates.values()),
        "scope": "early-mid first-eligible-root representation probe",
        "gates": gates,
        "threshold": selected_threshold,
        "selected_threshold_metrics": selected,
        "holdout_threshold_metrics": holdout,
        "holdout_cluster_bootstrap": bootstrap,
        "validation": validation,
        "validation_split_contract": split,
        "pooled_reference": {
            "best_overall_pairwise_accuracy": 0.5965095557057702,
            "best_outcome_pairwise_accuracy": 0.6279212792127922,
            "best_optimal_action_rate": 0.41990950226244345,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    decision = evaluate_probe(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(decision, sort_keys=True))
    if not decision["passed"]:
        raise SystemExit("structured action-value representation probe failed")


if __name__ == "__main__":
    main()
