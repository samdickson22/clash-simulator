from __future__ import annotations

import argparse

import pytest
import torch
from torch import nn

from scripts.pretrain_hog26_direct_simple_behavior import (
    _aggregate_metrics,
    _eligible,
    initialize_constant_event_mode,
    select_trainable_parameters,
)


class _ToyPolicy(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.actor_encoder = nn.Linear(2, 2)
        self.hierarchical_mode_gate = nn.Sequential(
            nn.Linear(2, 2), nn.GELU(), nn.Linear(2, 3)
        )


def test_aggregate_metrics_balances_timing_without_hiding_false_plays() -> None:
    metrics = _aggregate_metrics(
        [
            {
                "decision_loss": 1.0,
                "card_loss": 2.0,
                "tile_loss": 3.0,
                "rows": 10,
                "plays": 2,
                "waits": 8,
                "exact_correct": 8,
                "play_true_positive": 1,
                "play_false_positive": 1,
                "wait_correct": 7,
                "card_correct": 2,
                "tile_correct": 1,
                "play_probability_sum": 1.5,
                "play_brier_sum": 0.5,
                "hard_event_brier_sum": 0.6,
                "teacher_probability_sum": 1.2,
            },
            {
                "decision_loss": 2.0,
                "card_loss": 4.0,
                "tile_loss": 6.0,
                "rows": 20,
                "plays": 4,
                "waits": 16,
                "exact_correct": 15,
                "play_true_positive": 3,
                "play_false_positive": 2,
                "wait_correct": 14,
                "card_correct": 3,
                "tile_correct": 2,
                "play_probability_sum": 3.0,
                "play_brier_sum": 1.0,
                "hard_event_brier_sum": 1.4,
                "teacher_probability_sum": 2.4,
            },
        ]
    )
    assert metrics["loss"] == pytest.approx(10.0)
    assert metrics["exact_action_accuracy"] == pytest.approx(23 / 30)
    assert metrics["play_precision"] == pytest.approx(4 / 7)
    assert metrics["play_recall"] == pytest.approx(4 / 6)
    assert metrics["play_f1"] == pytest.approx(8 / 13)
    assert metrics["wait_accuracy"] == pytest.approx(21 / 24)
    assert metrics["balanced_timing_accuracy"] == pytest.approx(0.5 * (4 / 6 + 21 / 24))
    assert metrics["predicted_play_rate"] == pytest.approx(7 / 30)
    assert metrics["teacher_play_rate"] == pytest.approx(6 / 30)
    assert metrics["mean_play_probability"] == pytest.approx(4.5 / 30)
    assert metrics["play_brier"] == pytest.approx(1.5 / 30)
    assert metrics["hard_event_brier"] == pytest.approx(2.0 / 30)
    assert metrics["mean_teacher_play_probability"] == pytest.approx(3.6 / 30)
    assert metrics["card_accuracy"] == pytest.approx(5 / 6)
    assert metrics["tile_accuracy"] == pytest.approx(3 / 6)


def test_offline_gate_requires_precision_recall_and_conditional_heads() -> None:
    args = argparse.Namespace(
        minimum_play_precision=0.7,
        minimum_play_recall=0.7,
        minimum_wait_accuracy=0.95,
        minimum_card_accuracy=0.85,
        minimum_tile_accuracy=0.2,
        minimum_exact_action_accuracy=0.8,
    )
    passing = {
        "play_precision": 0.8,
        "play_recall": 0.8,
        "wait_accuracy": 0.96,
        "card_accuracy": 0.9,
        "tile_accuracy": 0.3,
        "exact_action_accuracy": 0.9,
    }
    assert _eligible(passing, args)
    for key in passing:
        failing = dict(passing)
        failing[key] = 0.0
        assert not _eligible(failing, args)


def test_mode_only_scope_freezes_every_non_timing_parameter() -> None:
    model = _ToyPolicy()
    names, parameters = select_trainable_parameters(model, "mode-only")  # type: ignore[arg-type]
    assert names == [
        "hierarchical_mode_gate.0.weight",
        "hierarchical_mode_gate.0.bias",
        "hierarchical_mode_gate.2.weight",
        "hierarchical_mode_gate.2.bias",
    ]
    assert parameters == list(model.hierarchical_mode_gate.parameters())
    assert all(
        not parameter.requires_grad for parameter in model.actor_encoder.parameters()
    )
    assert all(parameter.requires_grad for parameter in parameters)


def test_constant_event_initialization_sets_exact_train_only_probability() -> None:
    model = _ToyPolicy()
    model.config = argparse.Namespace(deterministic_hierarchy="event")
    initialize_constant_event_mode(model, 0.125)  # type: ignore[arg-type]
    inputs = torch.randn(7, 2)
    logits = model.hierarchical_mode_gate(inputs)
    probabilities = torch.softmax(logits[..., :2], dim=-1)[..., 0]
    torch.testing.assert_close(probabilities, torch.full((7,), 0.125))
    names, _parameters = select_trainable_parameters(  # type: ignore[arg-type]
        model, "mode-bias-only"
    )
    assert names == ["hierarchical_mode_gate.2.bias"]
