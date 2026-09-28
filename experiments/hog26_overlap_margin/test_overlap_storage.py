"""Convexity, clock-boundary continuity and per-expert weight allocation."""

import numpy as np
import pytest
from overlap_storage import blended_predict, overlap_weights
from phase_storage import normalized_phase_weights


class Constant:
    def __init__(self, value):
        self.value = value

    def predict(self, features):
        return np.full(len(features), self.value)


def test_gate_centers_partition_and_invalid_clock():
    clock = np.array([0, 1 / 6, 1 / 3, .5, 2 / 3, 5 / 6, 1, 1.1])
    expected = [[1, 0, 0], [1, 0, 0], [.5, .5, 0], [0, 1, 0], [0, .5, .5], [0, 0, 1], [0, 0, 1], [0, 0, 1]]
    np.testing.assert_allclose(overlap_weights(clock), expected, rtol=0, atol=3e-16)
    weights = overlap_weights(np.linspace(0, 1.1, 10001))
    assert np.all(weights >= 0)
    np.testing.assert_allclose(weights.sum(1), 1, rtol=0, atol=1e-15)
    for clock in (np.array([np.nan]), np.array([-1]), np.zeros((1, 1))):
        with pytest.raises(ValueError):
            overlap_weights(clock)


def test_fixed_expert_routing_has_no_old_boundary_jump_and_is_bounded():
    x = np.zeros((6, 814))
    epsilon = 1e-8
    x[:, 0] = [1 / 3 - epsilon, 1 / 3 + epsilon, 2 / 3 - epsilon, 2 / 3 + epsilon, 0, 1]
    prediction = blended_predict([Constant(-10), Constant(10), Constant(-10)], x, 0)
    # Clipping each head before combining makes the routing contribution
    # Lipschitz6 in the public clock for fixed head values.
    assert abs(prediction[1] - prediction[0]) <= 12 * epsilon + 1e-15
    assert abs(prediction[3] - prediction[2]) <= 12 * epsilon + 1e-15
    assert prediction[-2] == prediction[-1] == -1
    assert np.all(np.abs(prediction) <= 1)
    order = np.array([5, 0, 3, 1, 4, 2])
    np.testing.assert_array_equal(blended_predict([Constant(-10), Constant(10), Constant(-10)], x[order], 0), prediction[order])


def test_training_weights_follow_public_gate_without_changing_base_mass():
    original = np.array([.1, .2, .3, .4])
    saved = original.copy()
    clock = np.array([0, 1 / 3, .5, 1.])
    gated = original[:, None] * overlap_weights(clock)
    np.testing.assert_allclose(gated.sum(1), original)
    rows = np.flatnonzero(gated[:, 0] > 0)
    values = normalized_phase_weights(gated[:, 0], rows)
    np.testing.assert_allclose(values, [1, 1])
    np.testing.assert_array_equal(original, saved)
