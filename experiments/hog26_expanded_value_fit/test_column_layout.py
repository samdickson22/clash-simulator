"""Storage-layout equality and estimator invariance on synthetic public inputs."""

import numpy as np
from health_features import HealthLayout
from health_features import materialize_fitting as original_materialize
from value_models import new_trees
from value_storage import materialize_fitting


def test_column_layout_preserves_values_and_tree_predictions(tmp_path):
    rng = np.random.default_rng(311)
    source = rng.random((300, 809), dtype=np.float32)
    source[:, 6:12] = 1
    layout = HealthLayout(tuple(range(6)), tuple(range(6, 12)), tuple(range(36)))
    path = tmp_path / 'features.f32'
    source.tofile(path)
    rows = np.arange(0, 300, 2)
    before = original_materialize(path, source.shape, rows, layout, chunk_rows=31)
    after = materialize_fitting(path, source.shape, rows, layout, chunk_rows=29)
    assert before.flags.c_contiguous and after.flags.f_contiguous
    np.testing.assert_array_equal(before, after)
    classifiers, regressors = [], []
    weights = rng.random(len(rows))
    targets = rng.random(len(rows))
    for features in (before, after):
        classifier, regressor = new_trees(22, probe_iterations=2)
        classifiers.append(classifier.fit(features, np.arange(len(rows)) % 3, sample_weight=weights))
        regressors.append(regressor.fit(features, targets, sample_weight=weights))
    np.testing.assert_array_equal(classifiers[0].predict_proba(before), classifiers[1].predict_proba(before))
    np.testing.assert_array_equal(regressors[0].predict(before), regressors[1].predict(before))
