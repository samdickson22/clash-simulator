import numpy as np
import pytest
from fast_weights import fitting_weights
from scalar_evaluation import fitting_weights as reference_weights


@pytest.mark.parametrize("shuffle", [False, True])
def test_grouped_weights_are_exactly_the_original_formula(shuffle):
    rng = np.random.default_rng(19)
    lengths = [3, 17, 52, 101]
    ids = np.repeat(np.arange(4), lengths)
    progress = np.concatenate([np.linspace(0, stop, n) for n, stop in zip(lengths, [.2, .5, .8, 1.], strict=True)])
    fit = ids != 1
    if shuffle:
        order = rng.permutation(len(ids))
        ids, progress, fit = ids[order], progress[order], fit[order]
    expected = reference_weights(ids, progress, fit)
    actual = fitting_weights(ids, progress, fit)
    for a, b in zip(actual, expected, strict=True):
        np.testing.assert_array_equal(a, b)


def test_partial_game_fitting_membership_refuses():
    with pytest.raises(ValueError, match="membership changes"):
        fitting_weights(np.array([0, 0, 1, 1]), np.array([0., .5, 0., .5]), np.array([1, 0, 1, 1]))
