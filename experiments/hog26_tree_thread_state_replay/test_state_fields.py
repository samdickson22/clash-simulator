"""Normalization must reject learned-state changes while surviving serialization."""

import copy
import pickle

import numpy as np
from state_fields import state_fields
from value_models import new_trees


def test_field_state_roundtrip_and_mutation():
    rng = np.random.default_rng(31)
    x = rng.random((128, 814))
    model, _ = new_trees(71, probe_iterations=2)
    model.fit(x, np.arange(128) % 2 * 2)
    loaded = pickle.loads(pickle.dumps(model))
    assert state_fields(model) == state_fields(loaded)
    other = copy.deepcopy(loaded)
    other._bin_mapper.n_threads = 8
    assert state_fields(model) == state_fields(other)
    other._predictors[0][0].nodes['value'][-1] += .125
    assert state_fields(model) != state_fields(other)
