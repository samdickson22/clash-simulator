from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.finalize_hog26_phase_balanced_structured_rankers import (
    evaluate_reports,
)


def _report(seed: int, *, passing: bool = True) -> dict[str, object]:
    selection_games = list(range(51))
    calibration_games = list(range(51, 102))
    holdout_games = list(range(102, 170))
    lower = 0.7 if passing else 0.2
    accuracy = 0.75 if passing else 0.3
    return {
        "schema": "clasher.public_structured_action_value_fit.v2",
        "seed": seed,
        "corpus_sha256": "a" * 64,
        "validation_corpus_sha256": "b" * 64,
        "source_policy_sha256": "c" * 64,
        "config": {
            "state_size": 128,
            "recurrent_cell_size": 64,
            "play_hazard_size": 1,
        },
        "fit_contract": {
            "device": "cpu",
            "torch_version": "test",
            "epochs_requested": 120,
            "patience": 25,
            "batch_size": 96,
            "learning_rate": 3e-4,
            "weight_decay": 1e-4,
            "torch_threads": 4,
        },
        "minimum_score_gain": 0.5,
        "validation_split_contract": {
            "schema": "clasher.game_disjoint_selection_calibration_holdout.v1",
            "seed": 1169102,
            "games": {
                "selection": selection_games,
                "calibration": calibration_games,
                "holdout": holdout_games,
            },
            "states": {"selection": 200, "calibration": 200, "holdout": 300},
        },
        "selection": {
            "accuracy": accuracy,
            "outcome_accuracy": accuracy,
            "optimal_action_rate": accuracy,
        },
        "validation": {
            "accuracy": accuracy,
            "outcome_accuracy": accuracy,
            "optimal_action_rate": accuracy,
        },
        "calibration_sweep": [
            {
                "threshold": 0.5,
                "regressions": {"outcome": 0, "crown": 0, "damage": 0},
            }
        ],
        "holdout_threshold_metrics": {
            "overrides": 20,
            "improvements": {"outcome": 5, "crown": 3, "damage": 2},
            "regressions": {"outcome": 0, "crown": 0, "damage": 0},
        },
        "holdout_cluster_bootstrap": {
            "schema": "clasher.game_cluster_bootstrap.v1",
            "seed": 1169103,
            "samples": 10_000,
            "games": 68,
            "accuracy_games": 68,
            "outcome_accuracy_games": 50,
            "optimal_action_rate_games": 68,
            "accuracy_ci95": [lower, 0.9],
            "outcome_accuracy_ci95": [lower, 0.9],
            "optimal_action_rate_ci95": [lower, 0.9],
        },
    }


def test_phase_balanced_ranker_gate_selects_without_holdout_cherry_pick() -> None:
    reports = [_report(seed) for seed in (1176001, 1176002, 1176003)]
    reports[1]["selection"]["accuracy"] = 0.8
    result = evaluate_reports(reports)

    assert result["passed"]
    assert result["selected_seed"] == 1176002
    assert result["passing_seeds"] == ["1176001", "1176002", "1176003"]
    assert not result["promotion_authorized"]


def test_phase_balanced_ranker_gate_rejects_selected_seed_holdout_failure() -> None:
    reports = [_report(seed) for seed in (1176001, 1176002, 1176003)]
    reports[1]["selection"]["accuracy"] = 0.8
    reports[1]["validation"]["accuracy"] = 0.2

    result = evaluate_reports(reports)

    assert not result["passed"]
    assert result["selected_seed"] == 1176002
    assert result["passing_seeds"] == ["1176001", "1176003"]


def test_phase_balanced_ranker_gate_rejects_validation_overlap() -> None:
    reports = [_report(seed) for seed in (1176001, 1176002, 1176003)]
    broken = deepcopy(reports)
    broken[0]["validation_split_contract"]["games"]["holdout"][0] = 0

    with pytest.raises(ValueError, match="overlap"):
        evaluate_reports(broken)


def test_phase_balanced_ranker_gate_rejects_uncertified_mps_fit() -> None:
    reports = [_report(seed) for seed in (1176001, 1176002, 1176003)]
    reports[0]["fit_contract"]["device"] = "mps"

    with pytest.raises(ValueError, match="fit contract"):
        evaluate_reports(reports)
