"""Paired auxiliary uncertainty must preserve identity and scenario dependence."""

import numpy as np
import pytest
from binary_metrics import losses, paired_scores


def test_identity_swap_and_repeated_rows():
    labels = np.array([0, 0, 1, 1, 0, 1])
    clusters = np.array([0, 0, 1, 1, 2, 2])
    baseline = np.array([.3, .4, .6, .7, .2, .8])
    improved = np.array([.2, .3, .7, .8, .1, .9])
    zero = paired_scores(labels, baseline, baseline, clusters)
    assert all(value == 0 for metric in zero['metrics'].values() for value in metric.values())
    forward = paired_scores(labels, baseline, improved, clusters)
    reverse = paired_scores(labels, improved, baseline, clusters)
    repeated = paired_scores(np.repeat(labels, 2), np.repeat(baseline, 2), np.repeat(improved, 2), np.repeat(clusters, 2))
    for name, metric in forward['metrics'].items():
        assert metric['point'] > 0
        np.testing.assert_allclose(list(metric.values()), list(repeated['metrics'][name].values()), rtol=1e-14, atol=1e-14)
        assert np.isclose(metric['lower_95'], -reverse['metrics'][name]['upper_95'])
        assert np.isclose(metric['upper_95'], -reverse['metrics'][name]['lower_95'])
    assert repeated['scenario_clusters'] == 3


def test_invalid_labels_or_probabilities_refuse():
    for labels, probability in (([0, 2], [.2, .8]), ([0, 1], [.2, np.nan]), ([0, 1], [.2, 1.1]), ([], [])):
        with pytest.raises(ValueError, match='binary'):
            losses(labels, probability)
