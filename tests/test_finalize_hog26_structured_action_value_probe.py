from __future__ import annotations

from scripts.finalize_hog26_structured_action_value_probe import evaluate_probe


def _report() -> dict[str, object]:
    return {
        "schema": "clasher.public_structured_action_value_fit.v2",
        "minimum_score_gain": 0.5,
        "validation_split_contract": {
            "schema": "clasher.game_disjoint_selection_calibration_holdout.v1",
            "seed": 1169102,
            "games": {
                "selection": list(range(30)),
                "calibration": list(range(30, 60)),
                "holdout": list(range(60, 100)),
            },
            "states": {"selection": 30, "calibration": 30, "holdout": 50},
        },
        "selection": {"states": 30},
        "calibration": {"states": 30},
        "validation": {
            "states": 50,
            "accuracy": 0.64,
            "outcome_accuracy": 0.7,
            "optimal_action_rate": 0.44,
        },
        "calibration_sweep": [
            {
                "threshold": 0.5,
                "overrides": 40,
                "improvements": {"outcome": 10, "crown": 5, "damage": 5},
                "regressions": {"outcome": 0, "crown": 0, "damage": 0},
            }
        ],
        "holdout_threshold_metrics": {
            "threshold": 0.5,
            "states": 50,
            "overrides": 40,
            "improvements": {"outcome": 10, "crown": 5, "damage": 5},
            "regressions": {"outcome": 0, "crown": 0, "damage": 0},
            "optimal_action_rate": 0.44,
        },
        "holdout_cluster_bootstrap": {
            "schema": "clasher.game_cluster_bootstrap.v1",
            "seed": 1169103,
            "samples": 10000,
            "games": 40,
            "accuracy_games": 40,
            "accuracy_ci95": [0.61, 0.68],
            "outcome_accuracy_games": 32,
            "outcome_accuracy_ci95": [0.65, 0.75],
            "optimal_action_rate_games": 40,
            "optimal_action_rate_ci95": [0.43, 0.5],
        },
    }


def test_structured_probe_passes_only_material_safe_gain() -> None:
    decision = evaluate_probe(_report())

    assert decision["passed"] is True
    assert decision["promotion_authorized"] is False
    assert decision["phase_balanced_followup_required"] is True
    assert all(decision["gates"].values())


def test_structured_probe_rejects_pooled_level_outcome_accuracy() -> None:
    report = _report()
    report["validation"]["outcome_accuracy"] = 0.64  # type: ignore[index]

    decision = evaluate_probe(report)

    assert decision["passed"] is False
    assert decision["phase_balanced_followup_required"] is False
    assert decision["gates"]["outcome_pairwise_accuracy"] is False


def test_structured_probe_rejects_unsafe_threshold() -> None:
    report = _report()
    report["calibration_sweep"][0]["regressions"]["damage"] = 1  # type: ignore[index]

    decision = evaluate_probe(report)

    assert decision["passed"] is False
    assert decision["gates"]["zero_calibration_regressions"] is False


def test_structured_probe_rejects_unseen_holdout_regression() -> None:
    report = _report()
    report["holdout_threshold_metrics"]["regressions"]["damage"] = 1  # type: ignore[index]

    decision = evaluate_probe(report)

    assert decision["passed"] is False
    assert decision["gates"]["zero_holdout_regressions"] is False


def test_structured_probe_rejects_overlapping_validation_games() -> None:
    report = _report()
    report["validation_split_contract"]["games"]["holdout"] = [  # type: ignore[index]
        2,
        *range(61, 100),
    ]

    try:
        evaluate_probe(report)
    except ValueError as error:
        assert "overlap" in str(error)
    else:
        raise AssertionError("overlapping validation games should fail closed")


def test_structured_probe_rejects_cluster_uncertain_holdout() -> None:
    report = _report()
    report["holdout_cluster_bootstrap"]["outcome_accuracy_ci95"][0] = 0.62  # type: ignore[index]

    decision = evaluate_probe(report)

    assert decision["passed"] is False
    assert decision["gates"]["outcome_cluster_lower_above_pooled"] is False
