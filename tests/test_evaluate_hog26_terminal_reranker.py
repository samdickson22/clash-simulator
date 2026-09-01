from __future__ import annotations

import pytest

from scripts.evaluate_hog26_terminal_reranker import fixed_threshold_row


def test_fixed_threshold_row_requires_exact_frozen_threshold() -> None:
    metrics = {
        "threshold_curve": [
            {"threshold": 0.05, "improved_outcomes": 1},
            {"threshold": 0.1, "improved_outcomes": 2},
        ]
    }
    assert fixed_threshold_row(metrics, 0.1)["improved_outcomes"] == 2
    with pytest.raises(ValueError, match="absent or duplicated"):
        fixed_threshold_row(metrics, 0.2)
