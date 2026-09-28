import numpy as np
import pytest

pytest.importorskip("sklearn")

from scripts.hog26_tree_margin_diagnostic import fit_tree_margin


def test_withheld_targets_and_weights_cannot_change_tree_fit():
    rng = np.random.default_rng(81)
    features = rng.uniform(0, 1, (100, 20)).astype(np.float32)
    target = features[:, 0] * 0.3
    weights = np.ones(100, dtype=np.float32)
    fit_rows = np.arange(70)
    config = {"sklearn_version": "1.7.2", "learning_rate": 0.1,
              "max_iter": 5, "max_leaf_nodes": 5, "min_samples_leaf": 3,
              "l2_regularization": 1.0, "max_bins": 32}
    first = fit_tree_margin(features, target, weights, fit_rows, seed=1, config=config)
    target[70:] = -0.99
    weights[70:] = 1000
    second = fit_tree_margin(features, target, weights, fit_rows, seed=1, config=config)
    np.testing.assert_array_equal(first, second)
    assert np.isfinite(first).all()
    assert np.max(np.abs(first)) <= 1
