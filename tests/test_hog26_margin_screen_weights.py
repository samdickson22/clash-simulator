from __future__ import annotations

import numpy as np
import pytest
import torch

from scripts.screen_hog26_training_family_margin import fitting_phase_weights


def test_aggregate_phase_balance_uses_only_fitting_rows():
    phases = np.array([0, 0, 0, 1, 1, 2, 2, 0])
    weights = torch.tensor([1.0, 2.0, 3.0, 1.0, 2.0, 1.0, 1000.0, 1000.0])
    rows = np.arange(6)
    result = fitting_phase_weights(weights, phases, rows, aggregate_balance=True)
    assert result[6:].sum() == 0
    assert result[rows].mean() == pytest.approx(1.0)
    assert [result[phases == p].sum().item() for p in range(3)] == pytest.approx(
        [2.0, 2.0, 2.0]
    )
    changed = weights.clone()
    changed[6:] = 1e8
    torch.testing.assert_close(
        result, fitting_phase_weights(changed, phases, rows, aggregate_balance=True)
    )
    assert result[0] / result[1] == pytest.approx(0.5)


def test_legacy_weights_keep_their_fitting_row_ratios():
    weights = torch.tensor([1.0, 2.0, 3.0, 100.0])
    result = fitting_phase_weights(
        weights, np.array([0, 1, 2, 2]), np.arange(3), aggregate_balance=False
    )
    torch.testing.assert_close(result, torch.tensor([0.5, 1.0, 1.5, 0.0]))


def test_missing_fitting_phase_cannot_be_supplied_by_withheld_rows():
    with pytest.raises(ValueError, match="lacks"):
        fitting_phase_weights(
            torch.ones(3), np.array([0, 1, 2]), np.arange(2), aggregate_balance=True
        )
