from __future__ import annotations

import math

import numpy as np
import pytest

from clasher.rl.structured_obs import _unit_clip, _unit_clip_numpy


@pytest.mark.parametrize(
    "value",
    [
        -math.inf,
        -2.0,
        -0.0,
        0.0,
        np.nextafter(0.0, 1.0),
        0.25,
        np.nextafter(1.0, 0.0),
        1.0,
        np.nextafter(1.0, 2.0),
        2.0,
        math.inf,
        math.nan,
    ],
)
def test_scalar_unit_clip_matches_numpy_bits(value: float):
    expected = _unit_clip_numpy(value)
    actual = _unit_clip(value)

    if math.isnan(expected):
        assert math.isnan(actual)
        return
    expected_bits = np.asarray(expected, dtype=np.float64).view(np.uint64).item()
    actual_bits = np.asarray(actual, dtype=np.float64).view(np.uint64).item()
    assert actual_bits == expected_bits
