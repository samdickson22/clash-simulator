from __future__ import annotations

import numpy as np
import pytest

from scripts.audit_hog26_outcome_corpora import _reached_phases


def test_reached_phases_uses_exact_training_boundaries() -> None:
    progress = np.asarray([0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0])
    assert _reached_phases(progress) == ("early", "middle", "late")
    assert _reached_phases(np.asarray([0.2, 0.3])) == ("early",)


def test_reached_phases_rejects_nonfinite_progress() -> None:
    with pytest.raises(ValueError, match="finite vector"):
        _reached_phases(np.asarray([0.0, np.nan]))
