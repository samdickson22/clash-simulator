import numpy as np
import pytest

from scripts.hog26_public_history_features import public_history_features


def sample_public():
    rng = np.random.default_rng(7)
    public = rng.uniform(0, 1, (30, 18)).astype(np.float32)
    public[:, 0] = np.tile(np.arange(15) / 15, 2)
    public[:, 4] = 1
    return public


def test_future_rows_cannot_change_prefix_features():
    public = sample_public()
    original = public_history_features(public, np.array([0, 15, 30]))
    changed = public.copy()
    changed[9:15] *= 0.25
    changed[15:] *= 0.75
    actual = public_history_features(changed, np.array([0, 15, 30]))
    np.testing.assert_array_equal(actual[:9], original[:9])
    np.testing.assert_array_equal(original[:, -18:], public)


def test_history_resets_at_each_game():
    public = sample_public()
    together = public_history_features(public, np.array([0, 15, 30]))
    separate = public_history_features(public[15:], np.array([0, 15]))
    np.testing.assert_array_equal(together[15:], separate)
    np.testing.assert_array_equal(together[[0, 15], :55], 0)
    np.testing.assert_array_equal(together[[0, 15], 55], public[[0, 15], 1])


def test_changes_use_only_declared_past_windows():
    public = sample_public()
    result = public_history_features(public, np.array([0, 15, 30]))
    np.testing.assert_array_equal(result[10, :18], public[10] - public[9])
    np.testing.assert_array_equal(result[10, 18:36], public[10] - public[5])
    np.testing.assert_array_equal(result[10, 36:54], public[10] - public[0])
    assert np.isfinite(result).all()


@pytest.mark.parametrize("offsets", [[0, 0, 30], [1, 30], [0, 29], [0.0, 30.0]])
def test_invalid_boundaries_rejected(offsets):
    with pytest.raises(ValueError, match="boundaries"):
        public_history_features(sample_public(), np.array(offsets))
