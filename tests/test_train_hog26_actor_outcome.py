from __future__ import annotations

import numpy as np
import pytest
import torch

from clasher.rl.outcome_model import ActorOutcomeHead
from scripts.train_hog26_actor_outcome import (
    _binary_auc,
    _ece,
    _natural_metadata_values,
    _outcome_source,
    all_phase_decisive_auc_passed,
    episode_class_balanced_row_weights,
    metrics,
    outcome_epoch_selection_key,
)


def test_auc_and_ece_are_exact_on_separated_predictions() -> None:
    labels = torch.tensor([False, False, True, True])
    scores = torch.tensor([0.1, 0.2, 0.8, 0.9])
    assert _binary_auc(labels, scores) == 1.0
    probabilities = torch.tensor([[0.8, 0.2], [0.1, 0.9]])
    assert _ece(probabilities, torch.tensor([0, 1])) == pytest.approx(0.15)


def test_metrics_report_undiscounted_classes_and_margin() -> None:
    head = ActorOutcomeHead(18, hidden_size=2)
    with torch.no_grad():
        for parameter in head.parameters():
            parameter.zero_()
    result = metrics(
        head,
        torch.zeros(3, 18),
        torch.tensor([-1, 0, 1]),
        torch.tensor([-0.5, 0.0, 0.5]),
        device=torch.device("cpu"),
    )
    assert result["class_counts"] == {"loss": 1, "draw": 1, "win": 1}
    assert result["nll"] == pytest.approx((2.0 * np.log(4.0) + np.log(2.0)) / 3.0)
    assert result["brier"] == pytest.approx(17.0 / 24.0)
    assert result["tower_margin_mae"] == pytest.approx(1.0 / 3.0)
    assert result["decisive_win_loss_auc"] == pytest.approx(0.5)


def test_outcome_source_keeps_controlled_draws_separate() -> None:
    assert _outcome_source({"outcome_source": "natural-strategy-games"}) == (
        "natural-strategy-games"
    )
    assert _outcome_source({"symmetric_draw_source": True}) == (
        "controlled-symmetric-draws"
    )


def test_natural_metadata_values_excludes_controlled_draws() -> None:
    loaded = [
        (
            {"outcome_source": "natural-strategy-games", "opponents": ["balanced"]},
            object(),
        ),
        (
            {
                "outcome_source": "controlled-symmetric-draws",
                "opponents": ["symmetric-selfplay"],
            },
            object(),
        ),
    ]
    assert _natural_metadata_values(loaded, "opponents") == {"balanced"}  # type: ignore[arg-type]


def test_episode_class_balanced_weights_equalize_episodes_and_class_mass() -> None:
    from clasher.rl.direct_simple_behavior import DirectSimpleBehaviorCorpus

    corpus = DirectSimpleBehaviorCorpus(
        arrays={"final_outcomes": np.asarray([-1, -1, 1, 1, 1, 1], dtype=np.int8)},
        episode_offsets=np.asarray([0, 2, 6], dtype=np.int64),
        episode_stream_rows=np.asarray([0, 1], dtype=np.int64),
        episode_ordinals=np.asarray([0, 0], dtype=np.int64),
        initial_hidden=np.zeros((2, 1), dtype=np.float32),
        initial_cell=np.zeros((2, 1), dtype=np.float32),
    )
    weights = episode_class_balanced_row_weights(
        [({}, corpus)], target_class_mass=(0.5, 0.0, 0.5)
    ).numpy()
    assert weights[:2].sum() == pytest.approx(weights[2:].sum())
    assert weights[0] == pytest.approx(weights[1])
    assert weights[2] == pytest.approx(weights[5])


def test_epoch_selection_prefers_ranking_after_calibration_gate() -> None:
    def row(auc: float, nll: float, ece: float, draw_auc: float) -> dict[str, object]:
        return {
            "decisive_win_loss_auc": auc,
            "nll": nll,
            "ece_10": ece,
            "auc_one_vs_rest": {"draw": draw_auc},
        }

    def key(
        values: dict[str, object], *, acceptance_passed: bool
    ) -> tuple[int, float, float]:
        return outcome_epoch_selection_key(
            values,
            acceptance_passed=acceptance_passed,
        )

    assert key(row(0.70, 0.95, 0.15, 0.85), acceptance_passed=True) > key(
        row(0.61, 0.78, 0.12, 0.95), acceptance_passed=True
    )
    assert key(row(0.61, 0.78, 0.12, 0.95), acceptance_passed=True) > key(
        row(0.90, 0.70, 0.30, 0.99), acceptance_passed=False
    )


def test_all_phase_auc_rejects_missing_or_below_chance_phase() -> None:
    passing = {
        phase: {"decisive_win_loss_auc": value}
        for phase, value in (("early", 0.56), ("middle", 0.7), ("late", 0.9))
    }
    assert all_phase_decisive_auc_passed(passing, 0.55)
    passing["early"]["decisive_win_loss_auc"] = 0.54
    assert not all_phase_decisive_auc_passed(passing, 0.55)
    passing.pop("late")
    assert not all_phase_decisive_auc_passed(passing, 0.55)
