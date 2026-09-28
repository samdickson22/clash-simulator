import numpy as np
import pytest
from health_features import HealthLayout, augment, materialize_fitting


def fixture():
    values = np.zeros((4, 809), dtype=np.float32)
    values[:, 6:12] = 1
    values[:, :6] = [[0, .1, 1, .2, 0, 1], [.5, .4, 1, 0, .3, .8], [0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1]]
    return values, HealthLayout(tuple(range(6)), tuple(range(6, 12)), tuple(range(36)))


def test_health_features_preserve_inputs_and_ignore_destroyed_towers_in_minimum():
    values, layout = fixture()
    result = augment(values, layout)
    np.testing.assert_array_equal(result[:, :809], values)
    np.testing.assert_array_equal(result[:1, 809:811], np.array([[.1, .2]], dtype=np.float32))
    np.testing.assert_array_equal(result[2, 809:], np.zeros(5))
    np.testing.assert_array_equal(augment(values[:2], layout), result[:2])
    assert np.isfinite(result).all()


def test_unavailable_health_refuses():
    values, layout = fixture()
    values[0, 6] = 0
    with pytest.raises(ValueError, match="fully available"):
        augment(values, layout)


def test_chunked_fitting_matrix_keeps_exact_selected_rows(tmp_path):
    values, layout = fixture()
    path = tmp_path / "features.f32"
    values.tofile(path)
    rows = np.array([0, 2, 3])
    actual = materialize_fitting(path, values.shape, rows, layout, chunk_rows=1)
    assert actual.dtype == np.float64
    np.testing.assert_array_equal(actual, augment(values[rows], layout))
    with pytest.raises(ValueError, match="distinct ordered"):
        materialize_fitting(path, values.shape, np.array([2, 0]), layout)
