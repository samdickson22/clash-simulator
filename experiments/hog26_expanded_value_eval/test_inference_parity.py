"""Diagnostic batching must preserve actual estimator predictions at its boundary."""

import numpy as np
from evaluate import predict_tree_bundle
from value_models import canonical_probabilities, new_trees


def test_diagnostic_chunked_predictions_match_direct_estimators():
    rng = np.random.default_rng(43)
    features = rng.random((4201, 814), dtype=np.float32)
    features[:, -1] = features[:, -1] * 2 - 1
    classifier, regressor = new_trees(17, probe_iterations=2)
    classifier.fit(features[:100], np.arange(100) % 2 * 2)
    regressor.fit(features[:100], rng.random(100) * 2 - 1)
    probabilities, margin = predict_tree_bundle({'classifier': classifier, 'regressor': regressor}, features)
    np.testing.assert_array_equal(probabilities, canonical_probabilities(classifier, features))
    np.testing.assert_array_equal(margin, np.clip(features[:, -1] + regressor.predict(features), -1, 1))
