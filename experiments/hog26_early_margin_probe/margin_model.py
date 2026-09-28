"""Fixed absolute-error learner; only the public representation differs."""

import numpy as np
from value_models import new_trees


def make_model(seed, *, memory=False):
    _, model = new_trees(seed, probe_iterations=2 if memory else None)
    return model


def predict(model, features, current):
    return np.clip(current + model.predict(features), -1, 1)
