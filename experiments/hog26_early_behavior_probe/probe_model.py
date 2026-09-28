"""The same small histogram classifier for both public representations."""

import numpy as np
from value_models import new_trees


def make_model(seed, *, memory_probe=False):
    model, _ = new_trees(seed, probe_iterations=2 if memory_probe else None)
    return model


def probability(model, features):
    if not np.array_equal(model.classes_, np.array([0, 1])):
        raise ValueError('binary bridge-style labels must be zero and one')
    values = model.predict_proba(features)[:, 1]
    if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
        raise ValueError('invalid auxiliary probability')
    return values
