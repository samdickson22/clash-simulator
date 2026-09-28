"""Prevent a silent win/loss reversal when reading raw scalar WDL labels."""

import pytest
from build_cache import canonical_label


def test_explicit_raw_wdl_to_model_ldw_conversion():
    assert canonical_label([1, 0, 0]) == 2
    assert canonical_label([0, 1, 0]) == 1
    assert canonical_label([0, 0, 1]) == 0
    for invalid in ([0, 0, 0], [1, 1, 0], [0.2, 0.3, 0.5], [1, 0]):
        with pytest.raises(ValueError):
            canonical_label(invalid)
