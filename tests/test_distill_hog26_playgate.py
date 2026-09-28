from __future__ import annotations

import numpy as np
import pytest
import torch

from scripts.distill_hog26_playgate import (
    action_modes,
    episode_sequences,
    metrics_from_confusion,
)


def test_action_modes_factor_play_wait_and_ability() -> None:
    actions = torch.tensor([0, 575, 576, 2303, 2304, 2305])
    assert action_modes(actions).tolist() == [0, 0, 0, 0, 1, 2]


def test_mode_metrics_do_not_hide_all_wait_shortcut() -> None:
    metrics = metrics_from_confusion(
        np.asarray(
            [
                [0, 4, 0],
                [0, 96, 0],
                [0, 0, 0],
            ],
            dtype=np.int64,
        )
    )
    assert metrics["accuracy"] == pytest.approx(0.96)
    assert metrics["wait_accuracy"] == pytest.approx(1.0)
    assert metrics["play_recall"] == pytest.approx(0.0)
    assert metrics["play_f1"] == pytest.approx(0.0)


def test_episode_sequences_require_contiguous_rows() -> None:
    sequences = episode_sequences(np.asarray([4, 4, 9, 9, 9]))
    assert [rows.tolist() for rows in sequences] == [[0, 1], [2, 3, 4]]
    with pytest.raises(ValueError, match="contiguous"):
        episode_sequences(np.asarray([4, 9, 4]))
