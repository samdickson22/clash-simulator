"""Select and gate three phase-balanced structured ranker seeds."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_SEEDS = frozenset({1176001, 1176002, 1176003})
REFERENCE = {
    "accuracy": 0.5965095557057702,
    "outcome_accuracy": 0.6279212792127922,
    "optimal_action_rate": 0.41990950226244345,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _regression_count(metrics: dict[str, Any]) -> int:
    return sum(int(value) for value in metrics["regressions"].values())


def _improvement_count(metrics: dict[str, Any]) -> int:
    return sum(int(value) for value in metrics["improvements"].values())


def _selection_key(report: dict[str, Any]) -> tuple[float, ...]:
    selection = report["selection"]
    normalized = (
        float(selection["accuracy"]) / 0.62,
        float(selection["outcome_accuracy"]) / 0.67,
        float(selection["optimal_action_rate"])
        / REFERENCE["optimal_action_rate"],
    )
    return (
        min(normalized),
        sum(normalized) / len(normalized),
        float(selection["outcome_accuracy"]),
        float(selection["optimal_action_rate"]),
        -float(report["seed"]),
    )


def _seed_gate(report: dict[str, Any]) -> dict[str, Any]:
    validation = report["validation"]
    threshold = report["holdout_threshold_metrics"]
    bootstrap = report["holdout_cluster_bootstrap"]
    gates = {
        "overall_accuracy": float(validation["accuracy"]) >= 0.62,
        "outcome_accuracy": float(validation["outcome_accuracy"]) >= 0.67,
        "optimal_action_rate": float(validation["optimal_action_rate"])
        > REFERENCE["optimal_action_rate"],
        "minimum_safe_overrides": int(threshold["overrides"]) >= 15,
        "minimum_safe_improvements": _improvement_count(threshold) >= 10,
        "zero_calibration_regressions": all(
            _regression_count(row) == 0
            for row in report["calibration_sweep"]
            if float(row["threshold"]) == float(report["minimum_score_gain"])
        ),
        "zero_holdout_regressions": _regression_count(threshold) == 0,
        "overall_cluster_lower_above_reference": float(
            bootstrap["accuracy_ci95"][0]
        )
        > REFERENCE["accuracy"],
        "outcome_cluster_lower_above_reference": float(
            bootstrap["outcome_accuracy_ci95"][0]
        )
        > REFERENCE["outcome_accuracy"],
        "optimal_cluster_lower_above_reference": float(
            bootstrap["optimal_action_rate_ci95"][0]
        )
        > REFERENCE["optimal_action_rate"],
    }
    return {
        "passed": all(gates.values()),
        "gates": gates,
        "selection_key": list(_selection_key(report)),
        "validation": validation,
        "holdout_threshold_metrics": threshold,
        "holdout_cluster_bootstrap": bootstrap,
    }


def evaluate_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if len(reports) != 3:
        raise ValueError("phase-balanced ranker gate requires exactly three seeds")
    by_seed = {int(report["seed"]): report for report in reports}
    if set(by_seed) != EXPECTED_SEEDS or len(by_seed) != len(reports):
        raise ValueError("phase-balanced ranker seeds changed")
    authorities = {
        (
            report.get("corpus_sha256"),
            report.get("validation_corpus_sha256"),
            report.get("source_policy_sha256"),
        )
        for report in reports
    }
    if len(authorities) != 1 or any(None in row for row in authorities):
        raise ValueError("phase-balanced rankers use different authorities")
    validation_partitions = []
    for report in reports:
        if report.get("schema") != "clasher.public_structured_action_value_fit.v2":
            raise ValueError("unsupported structured ranker report")
        config = report["config"]
        if (
            int(config.get("state_size", -1)) != 128
            or int(config.get("recurrent_cell_size", -1)) != 64
            or int(config.get("play_hazard_size", -1)) != 1
        ):
            raise ValueError("phase-balanced ranker state contract changed")
        fit_contract = report.get("fit_contract")
        if not isinstance(fit_contract, dict) or {
            "device": fit_contract.get("device"),
            "epochs_requested": int(fit_contract.get("epochs_requested", -1)),
            "patience": int(fit_contract.get("patience", -1)),
            "batch_size": int(fit_contract.get("batch_size", -1)),
            "learning_rate": float(fit_contract.get("learning_rate", -1.0)),
            "weight_decay": float(fit_contract.get("weight_decay", -1.0)),
            "torch_threads": int(fit_contract.get("torch_threads", -1)),
        } != {
            "device": "cpu",
            "epochs_requested": 120,
            "patience": 25,
            "batch_size": 96,
            "learning_rate": 3e-4,
            "weight_decay": 1e-4,
            "torch_threads": 4,
        }:
            raise ValueError("phase-balanced ranker fit contract changed")
        split = report["validation_split_contract"]
        if (
            split.get("schema")
            != "clasher.game_disjoint_selection_calibration_holdout.v1"
            or int(split.get("seed", -1)) != 1169102
        ):
            raise ValueError("phase-balanced validation split changed")
        games = {
            name: tuple(int(value) for value in split["games"][name])
            for name in ("selection", "calibration", "holdout")
        }
        if {name: len(values) for name, values in games.items()} != {
            "selection": 51,
            "calibration": 51,
            "holdout": 68,
        }:
            raise ValueError("phase-balanced validation game counts changed")
        if (
            set(games["selection"]) & set(games["calibration"])
            or set(games["selection"]) & set(games["holdout"])
            or set(games["calibration"]) & set(games["holdout"])
        ):
            raise ValueError("phase-balanced validation games overlap")
        validation_partitions.append(games)
        bootstrap = report["holdout_cluster_bootstrap"]
        if (
            bootstrap.get("schema") != "clasher.game_cluster_bootstrap.v1"
            or int(bootstrap.get("seed", -1)) != 1169103
            or int(bootstrap.get("samples", 0)) != 10_000
            or int(bootstrap.get("games", 0)) != 68
            or int(bootstrap.get("accuracy_games", 0)) != 68
            or int(bootstrap.get("optimal_action_rate_games", 0)) != 68
            or int(bootstrap.get("outcome_accuracy_games", 0)) < 34
        ):
            raise ValueError("phase-balanced clustered holdout contract changed")
    if any(partition != validation_partitions[0] for partition in validation_partitions):
        raise ValueError("phase-balanced seeds use different validation games")

    selected_seed = max(by_seed, key=lambda seed: _selection_key(by_seed[seed]))
    seed_results = {
        str(seed): _seed_gate(by_seed[seed]) for seed in sorted(by_seed)
    }
    passing_seeds = [
        seed for seed, result in seed_results.items() if result["passed"]
    ]
    passed = bool(
        len(passing_seeds) >= 2 and seed_results[str(selected_seed)]["passed"]
    )
    return {
        "schema": "clasher.hog26_phase_balanced_structured_ranker_gate.v1",
        "passed": passed,
        "offline_gate_passed": passed,
        "promotion_authorized": False,
        "gameplay_screen_authorized": passed,
        "selected_seed": selected_seed,
        "selection_rule": "best-selection-split-normalized-gate-balance-v1",
        "passing_seeds": passing_seeds,
        "required_passing_seeds": 2,
        "reference": REFERENCE,
        "authorities": list(next(iter(authorities))),
        "seeds": seed_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.input]
    result = evaluate_reports(reports)
    result["inputs"] = {str(path.resolve()): _sha256(path) for path in args.input}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    if not result["passed"]:
        raise SystemExit("phase-balanced structured ranker offline gate failed")


if __name__ == "__main__":
    main()
