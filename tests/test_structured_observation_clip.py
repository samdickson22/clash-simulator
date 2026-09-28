import math

import numpy as np
import pytest

from clasher.rl.structured_obs import (
    _range_clip_numpy,
    _range_clip_scalar,
    _unit_clip,
    _unit_clip_numpy,
)


@pytest.mark.parametrize(
    "value",
    [-math.inf, -2.0, -0.0, 0.0, 0.25, 1.0, 2.0, math.inf, math.nan],
)
def test_scalar_unit_clip_matches_numpy_bits(value: float) -> None:
    expected = _unit_clip_numpy(value)
    actual = _unit_clip(value)
    if math.isnan(expected):
        assert math.isnan(actual)
        return
    expected_bits = np.asarray(expected, dtype=np.float64).view(np.uint64).item()
    actual_bits = np.asarray(actual, dtype=np.float64).view(np.uint64).item()
    assert actual_bits == expected_bits


@pytest.mark.parametrize("lower,upper", [(-1.0, 1.0), (0.0, 4.0)])
@pytest.mark.parametrize(
    "value",
    [-math.inf, -2.0, -0.0, 0.0, 0.25, 1.0, 4.0, 5.0, math.inf, math.nan],
)
def test_scalar_range_clip_matches_numpy_bits(
    value: float,
    lower: float,
    upper: float,
) -> None:
    expected = _range_clip_numpy(value, lower, upper)
    actual = _range_clip_scalar(value, lower, upper)
    if math.isnan(expected):
        assert math.isnan(actual)
        return
    expected_bits = np.asarray(expected, dtype=np.float64).view(np.uint64).item()
    actual_bits = np.asarray(actual, dtype=np.float64).view(np.uint64).item()
    assert actual_bits == expected_bits
