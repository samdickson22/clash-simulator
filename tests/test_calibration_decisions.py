"""Decision calibration must not hide tie regret, false outcomes, or dependence."""

import pytest
from pydantic import ValidationError

from clasher.rl.calibration_decisions import (
    CandidatePair,
    DecisionCriteria,
    DecisionRoot,
    development_summary,
    root_metrics,
)


def criteria():
    return DecisionCriteria(
        minimum_families=64,
        confidence=0.95,
        maximum_bad_family_rate=0.05,
        hp_regret_tolerance=81.0,
        minimum_clear_improvement_families=5,
    )


def root(pairs, root_id="r", family="f"):
    return DecisionRoot(
        root_id=root_id,
        family_id=family,
        baseline="recorded",
        expected_candidates=("wait", "recorded"),
        candidates=tuple(
            CandidatePair(
                name=n,
                native_outcome=no,
                native_hp_margin=float(nh),
                scalar_outcome=so,
                scalar_hp_margin=float(sh),
            )
            for n, no, nh, so, sh in pairs
        ),
    )


def test_worst_scalar_tie_is_used():
    r = root([("wait", 1, 500, 1, 500), ("recorded", 1, 200, 1, 500)])
    a = root_metrics(r, criteria())
    assert a["worst_chosen_hp_regret"] == 300
    assert a["bad_decision"]


def test_false_win_is_bad_even_when_all_native_actions_lose():
    r = root([("wait", -1, 0, -1, 0), ("recorded", -1, 100, 1, 100)])
    a = root_metrics(r, criteria())
    assert a["worst_chosen_outcome_regret"] == 0
    assert a["selected_outcome_mismatch"] and a["bad_decision"]


def test_related_roots_count_as_one_family_and_never_pass_acceptance():
    pairs = [("wait", 1, 500, 1, 500), ("recorded", 1, 200, 1, 200)]
    a = development_summary([root(pairs, "a"), root(pairs, "b")], criteria())
    assert a["root_count"] == 2 and a["family_count"] == 1
    assert a["clear_improvement_families"] == 1
    assert a["confidence_bound_from_observed_data"] is None
    assert not a["acceptance_passed"] and not a["training_authorized"]


def test_duplicate_roots_and_missing_candidates_fail():
    r = root([("wait", 1, 500, 1, 500), ("recorded", 1, 200, 1, 200)])
    with pytest.raises(ValueError, match="duplicate root"):
        development_summary([r, r], criteria())
    with pytest.raises(ValidationError, match="missing declared"):
        DecisionRoot(
            root_id="r",
            family_id="f",
            baseline="recorded",
            expected_candidates=("wait", "recorded", "delay"),
            candidates=r.candidates,
        )


def test_zero_failure_sample_size_is_not_inferred_from_opened_pilot():
    assert criteria().planned_zero_failure_upper_bound == pytest.approx(
        0.0457297, abs=1e-6
    )
    with pytest.raises(ValidationError, match="family count"):
        DecisionCriteria(
            minimum_families=32,
            confidence=0.95,
            maximum_bad_family_rate=0.05,
            hp_regret_tolerance=81.0,
            minimum_clear_improvement_families=5,
        )


def test_nonfinite_outcome_and_boolean_result_are_rejected():
    with pytest.raises(ValidationError):
        CandidatePair(
            name="wait",
            native_outcome=True,
            native_hp_margin=0.0,
            scalar_outcome=1,
            scalar_hp_margin=0.0,
        )
    with pytest.raises(ValidationError):
        CandidatePair(
            name="wait",
            native_outcome=1,
            native_hp_margin=float("nan"),
            scalar_outcome=1,
            scalar_hp_margin=0.0,
        )
