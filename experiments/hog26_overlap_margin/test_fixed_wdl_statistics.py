"""Require complete equality to the original bootstrap, including tied-score AUC."""

import numpy as np
import pytest
from fixed_wdl_statistics import reuse_wdl_bootstrap
from scalar_evaluation import cluster_bootstrap


@pytest.mark.parametrize('single_outcome', [False, True])
def test_exact_complete_bootstrap_equivalence(single_outcome):
    rng = np.random.default_rng(23)
    n = 72
    probability = rng.dirichlet([2., .1, 2.], size=n)
    probability[1::3] = probability[::3]
    labels = np.zeros(n, dtype=np.int64) if single_outcome else np.tile(np.array([0, 2, 1, 2, 0, 2]), 12)
    target = rng.uniform(-1, 1, n)
    current = rng.uniform(-.5, .5, n)
    old_margin = np.clip(current + rng.normal(0, .1, n), -1, 1)
    new_margin = np.clip(current + rng.normal(0, .1, n), -1, 1)
    weights = rng.uniform(.01, 1, n)
    weights[::7] = 0
    weights /= weights.sum()
    clusters = np.repeat(np.arange(n // 2), 2)
    prior = np.tile(np.array([.6, .01, .39]), (n, 1))
    reference = cluster_bootstrap(probability, labels, old_margin, target, current, weights, prior, clusters)
    expected = cluster_bootstrap(probability, labels, new_margin, target, current, weights, prior, clusters)
    actual = reuse_wdl_bootstrap(probability, probability.copy(), labels, new_margin, target, current, weights, prior, clusters, reference)
    assert actual == expected
    changed = probability.copy()
    changed[0] = changed[0, ::-1]
    with pytest.raises(ValueError, match='byte-identical'):
        reuse_wdl_bootstrap(changed, probability, labels, new_margin, target, current, weights, prior, clusters, reference)
