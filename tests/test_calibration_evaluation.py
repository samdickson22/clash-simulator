"""Incomplete or dependent cases must not inflate family-level gate metrics."""

import pytest

from clasher.rl.calibration_decisions import (
    CandidatePair,
    DecisionCriteria,
    DecisionRoot,
)
from clasher.rl.calibration_evaluation import RootAssessment, evaluate_family_metrics


def criteria(minimum=2):
    return DecisionCriteria(
        minimum_families=minimum,
        confidence=0.5,
        maximum_bad_family_rate=0.6,
        hp_regret_tolerance=81.0,
        minimum_clear_improvement_families=1,
    )


def assessment(family, config, kind="good"):
    pairs = [("recorded", 1, 0.0, 1, 0.0), ("wait", 1, 200.0, 1, 200.0)]
    if kind == "false_win":
        pairs = [("recorded", -1, 0.0, -1, 0.0), ("wait", -1, 200.0, 1, 200.0)]
    if kind == "regression":
        pairs = [("recorded", 1, 200.0, 1, 0.0), ("wait", 1, 0.0, 1, 200.0)]
    decision = DecisionRoot(
        root_id=config,
        family_id=family,
        baseline="recorded",
        expected_candidates=("recorded", "wait"),
        candidates=tuple(
            CandidatePair(
                name=n,
                native_outcome=no,
                native_hp_margin=nh,
                scalar_outcome=so,
                scalar_hp_margin=sh,
            )
            for n, no, nh, so, sh in pairs
        ),
    )
    return RootAssessment(
        family_id=family,
        config_sha256=config,
        decision=decision,
        public_errors=("wrong level",) if kind == "public_failure" else (),
    )


def test_complete_metrics_do_not_grant_provenance_or_training_admission():
    expected = {"a": ("a" * 64, "b" * 64), "b": ("c" * 64,)}
    result = evaluate_family_metrics(
        expected,
        [assessment(f, r) for f, rs in expected.items() for r in rs],
        criteria(),
    )
    assert result["metrics_passed"] and result["family_count"] == 2
    assert result["clear_improvement_families"] == 2
    assert not result["acceptance_passed"] and not result["training_authorized"]


def test_two_seats_do_not_count_as_two_independent_families():
    expected = {"a": ("a" * 64, "b" * 64)}
    result = evaluate_family_metrics(
        expected, [assessment("a", r) for r in expected["a"]], criteria()
    )
    assert result["family_count"] == 1 and not result["metrics_passed"]


def test_missing_declared_configuration_fails_entire_family():
    result = evaluate_family_metrics(
        {"a": ("a" * 64, "b" * 64)}, [assessment("a", "a" * 64)], criteria(1)
    )
    assert (
        result["public_failed_families"] == 1 and result["ranking_failed_families"] == 1
    )
    assert result["clear_improvement_families"] == 0 and not result["metrics_passed"]


@pytest.mark.parametrize("kind", ["false_win", "regression", "public_failure"])
def test_one_bad_member_cannot_hide_behind_improved_peer(kind):
    result = evaluate_family_metrics(
        {"a": ("a" * 64, "b" * 64)},
        [assessment("a", "a" * 64), assessment("a", "b" * 64, kind)],
        criteria(1),
    )
    assert (
        result["ranking_failed_families"] == 1
        and result["clear_improvement_families"] == 0
    )
    assert not result["metrics_passed"]


def test_missing_root_has_no_zero_regret_imputation():
    row = RootAssessment(
        family_id="a", config_sha256="a" * 64, branch_errors=("no eligible root",)
    )
    result = evaluate_family_metrics({"a": ("a" * 64,)}, [row], criteria(1))
    assert result["public_metrics_passed"]
    assert not result["ranking_metrics_passed"]
    assert result["families"][0]["members"][0]["decision"] is None


def test_duplicate_or_undeclared_evidence_rejected():
    row = assessment("a", "a" * 64)
    with pytest.raises(ValueError, match="duplicate assessment"):
        evaluate_family_metrics({"a": ("a" * 64,)}, [row, row], criteria(1))
    with pytest.raises(ValueError, match="undeclared"):
        evaluate_family_metrics({"b": ("b" * 64,)}, [row], criteria(1))
    with pytest.raises(ValueError, match="overlapping"):
        evaluate_family_metrics({"a": ("a" * 64,), "b": ("a" * 64,)}, [], criteria(1))
    duplicate = row.model_copy(update={"config_sha256": "b" * 64})
    with pytest.raises(ValueError, match="multiple configurations"):
        evaluate_family_metrics(
            {"a": ("a" * 64, "b" * 64)}, [row, duplicate], criteria(1)
        )
