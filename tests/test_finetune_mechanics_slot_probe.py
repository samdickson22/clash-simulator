from __future__ import annotations

import pytest

from scripts.finetune_mechanics_slot_probe import (
    _promotion_decision,
    _safe_epoch_score,
)


def test_safe_epoch_score_rejects_a_human_gain_that_breaks_either_guard() -> None:
    human = {"accuracy": 0.6, "loss": 1.0}
    baselines = {
        "validation": {"accuracy": 0.85, "loss": 0.0},
        "heldout": {"accuracy": 0.80, "loss": 0.0},
    }

    assert (
        _safe_epoch_score(
            human_validation=human,
            guard_metrics={
                "validation": {"accuracy": 0.84, "loss": 0.0},
                "heldout": {"accuracy": 0.789, "loss": 0.0},
            },
            guard_baselines=baselines,
            max_guard_regression=0.01,
        )
        is None
    )


def test_safe_epoch_score_uses_human_accuracy_then_nll() -> None:
    score = _safe_epoch_score(
        human_validation={"accuracy": 0.6, "loss": 1.25},
        guard_metrics={"validation": {"accuracy": 0.84, "loss": 0.0}},
        guard_baselines={"validation": {"accuracy": 0.85, "loss": 0.0}},
        max_guard_regression=0.01,
    )

    assert score == (0.6, -1.25)


def _gate_metrics(*, human: float, validation: float, heldout: float) -> dict:
    return {
        "human_validation": {"accuracy": human},
        "simulator_validation": {"accuracy": validation},
        "simulator_heldout": {"accuracy": heldout},
    }


def test_promotion_requires_material_human_gain_and_both_guards() -> None:
    control = _gate_metrics(human=0.50, validation=0.85, heldout=0.80)

    assert not _promotion_decision(
        control_metrics=control,
        candidate_metrics=_gate_metrics(human=0.509, validation=0.85, heldout=0.80),
        min_human_validation_gain=0.01,
        max_simulator_regression=0.01,
    )
    assert not _promotion_decision(
        control_metrics=control,
        candidate_metrics=_gate_metrics(human=0.52, validation=0.839, heldout=0.80),
        min_human_validation_gain=0.01,
        max_simulator_regression=0.01,
    )
    assert _promotion_decision(
        control_metrics=control,
        candidate_metrics=_gate_metrics(human=0.51, validation=0.84, heldout=0.79),
        min_human_validation_gain=0.01,
        max_simulator_regression=0.01,
    )


def test_promotion_rejects_negative_tolerances() -> None:
    metrics = _gate_metrics(human=0.50, validation=0.85, heldout=0.80)
    with pytest.raises(ValueError, match="min_human_validation_gain"):
        _promotion_decision(
            control_metrics=metrics,
            candidate_metrics=metrics,
            min_human_validation_gain=-0.01,
            max_simulator_regression=0.01,
        )
