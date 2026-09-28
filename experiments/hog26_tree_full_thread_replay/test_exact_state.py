"""Exactness checks must retain signed zero and distinguish learned-state changes."""

import copy

import numpy as np
from probe import canonical_state
from replay import array_digest
from value_models import new_trees


def test_array_digest_includes_precision_and_signed_zero():
    assert array_digest(np.array([0.], dtype=np.float64)) != array_digest(np.array([-0.], dtype=np.float64))
    assert array_digest(np.array([1.], dtype=np.float64)) != array_digest(np.array([1.], dtype=np.float32))
    assert array_digest(np.array([[1., 2.]], order='C')) == array_digest(np.array([[1., 2.]], order='F'))


def test_only_execution_field_is_normalized():
    rng = np.random.default_rng(84)
    features = rng.random((64, 814))
    model, _ = new_trees(31, probe_iterations=2)
    model.fit(features, np.arange(64) % 2 * 2)
    changed = copy.deepcopy(model)
    changed._bin_mapper.n_threads = 8
    assert canonical_state(model) == canonical_state(changed)
    changed._predictors[0][0].nodes['value'][-1] += .125
    assert canonical_state(model) != canonical_state(changed)
