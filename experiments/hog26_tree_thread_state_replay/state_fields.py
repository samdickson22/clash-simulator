"""Exact estimator fields without cross-field pickle memoization artifacts."""

import copy
import hashlib
import pickle


def state_fields(model):
    copied = copy.deepcopy(model)
    copied._bin_mapper.n_threads = 1
    return {'estimator_type': type(copied).__module__ + '.' + type(copied).__qualname__,
            'fields': {name: hashlib.sha256(pickle.dumps(value, protocol=5)).hexdigest()
                       for name, value in sorted(vars(copied).items())}}
