from __future__ import annotations

import numpy as np
import pytest

from clasher.rl.complete_outcomes import complete_outcome_labels


def _globals(rows: int) -> np.ndarray:
    values = np.zeros((rows, 18), dtype=np.float32)
    values[:, 8:14] = 1.0
    return values


def test_complete_outcomes_repeat_learner_relative_labels_and_public_margin() -> None:
    globals_ = _globals(5)
    globals_[1, 8:11] = [1.0, 0.5, 1.0]
    globals_[1, 11:14] = [0.0, 1.0, 1.0]
    globals_[4, 8:11] = [0.2, 0.4, 1.0]
    globals_[4, 11:14] = [0.5, 0.5, 1.0]
    result = complete_outcome_labels(
        episode_offsets=np.asarray([0, 2, 5], dtype=np.int64),
        dones=np.asarray([False, True, False, False, True]),
        terminal_winners=np.asarray([-1, 1, -1, -1, 1]),
        next_global_features=globals_,
        episode_learner_players=np.asarray([1, 0]),
    )
    assert result.episode_final_outcomes.tolist() == [1, -1]
    assert result.final_outcomes.tolist() == [1, 1, -1, -1, -1]
    assert result.episode_terminal_tower_margins.tolist() == pytest.approx(
        [1.0 / 6.0, -0.4 / 3.0]
    )
    assert result.terminal_tower_margins.tolist() == pytest.approx(
        [1.0 / 6.0, 1.0 / 6.0, -0.4 / 3.0, -0.4 / 3.0, -0.4 / 3.0]
    )


def test_complete_outcomes_reject_incomplete_or_nonpublic_labels() -> None:
    with pytest.raises(ValueError, match="first-terminal"):
        complete_outcome_labels(
            episode_offsets=np.asarray([0, 2], dtype=np.int64),
            dones=np.asarray([True, True]),
            terminal_winners=np.asarray([0, 0]),
            next_global_features=_globals(2),
            episode_learner_players=np.asarray([0]),
        )
    broken = _globals(2)
    broken[1, 8] = 1.5
    with pytest.raises(ValueError, match="tower fractions"):
        complete_outcome_labels(
            episode_offsets=np.asarray([0, 2], dtype=np.int64),
            dones=np.asarray([False, True]),
            terminal_winners=np.asarray([-1, 0]),
            next_global_features=broken,
            episode_learner_players=np.asarray([0]),
        )
