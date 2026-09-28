"""Boundary routing and preservation of within-phase weight ratios."""

import numpy as np
import pytest
from phase_storage import normalized_phase_weights, routed_predict


class Constant:
    def __init__(self, value):
        self.value = value

    def predict(self, features):
        return np.full(len(features), self.value)


def test_public_clock_boundaries_clip_and_row_order():
    x = np.zeros((7, 814))
    x[:, 0] = [1., 0., 1 / 3, 2 / 3, np.nextafter(1 / 3, 0), np.nextafter(2 / 3, 0), 1.2]
    x[:, -1] = [.9, -.9, 0, 0, 0, 0, -.1]
    actual = routed_predict([Constant(-.2), Constant(.1), Constant(.3)], x, 0)
    np.testing.assert_allclose(actual, [1., -1., .1, .3, -.2, .1, .2])
    order = np.array([6, 0, 3, 1, 5, 2, 4])
    np.testing.assert_array_equal(routed_predict([Constant(-.2), Constant(.1), Constant(.3)], x[order], 0), actual[order])
    with pytest.raises(ValueError):
        routed_predict([Constant(0)] * 3, np.full((1, 814), np.nan), 0)


def test_phase_weights_preserve_ratios_and_mean_one():
    weights = np.array([.01, .04, .2, .75])
    rows = np.array([0, 2])
    normalized = normalized_phase_weights(weights, rows)
    assert normalized.mean() == pytest.approx(1.)
    assert normalized[1] / normalized[0] == pytest.approx(20.)
    np.testing.assert_allclose(normalized, normalized_phase_weights(weights * 7, rows), rtol=1e-15, atol=0)
    with pytest.raises(ValueError):
        normalized_phase_weights(weights, np.zeros(0, dtype=int))
