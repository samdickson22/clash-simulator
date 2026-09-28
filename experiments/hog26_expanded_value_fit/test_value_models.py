"""Class mapping and exact cached training equivalence on synthetic public data."""

from types import SimpleNamespace

import numpy as np
import pytest
import torch
from scalar_training import fit_globals
from value_models import canonical_probabilities, fit_cached_globals


def test_absent_draw_class_is_explicit():
    model = SimpleNamespace(classes_=np.array([0, 2]), predict_proba=lambda x: np.tile([.3, .7], (len(x), 1)))
    np.testing.assert_array_equal(canonical_probabilities(model, np.zeros((2, 814))), [[.3, 0, .7], [.3, 0, .7]])
    model.classes_ = np.array([0, 4])
    with pytest.raises(ValueError, match='canonical'):
        canonical_probabilities(model, np.zeros((2, 814)))


def test_cached_training_matches_original_forward_exactly():
    torch.set_num_threads(1)
    rng = np.random.default_rng(213)
    games, features, weights, labels = [], [], [], []
    for label, count in ((0, 13), (2, 17), (0, 7)):
        g = rng.random((count, 18), dtype=np.float32)
        c = rng.choice(np.array([0, .5, 1], dtype=np.float32), (count, 18))
        games.append(SimpleNamespace(public={'global_features': g, 'global_feature_confidence': c}, target_class=label))
        features.append(np.concatenate((np.where(c > 0, g * c, 0), c), axis=1))
        weights.append(np.full(count, 1 / (3 * count)))
        labels.extend([label] * count)
    original = fit_globals(games, list(range(3)), weights, seed=21, epochs=3, batch_rows=8)
    cached = fit_cached_globals(np.concatenate(features), np.array(labels), np.concatenate(weights), seed=21, epochs=3, batch_rows=8)
    for name, value in original.state_dict().items():
        assert torch.equal(value, cached.state_dict()[name]), name
