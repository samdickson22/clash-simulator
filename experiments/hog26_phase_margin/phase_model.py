"""Fixed phase regressors and verified bounded OpenMP fitting context."""

import torch
from value_models import new_trees


def fit_model(features, target, weights, seed, *, memory=False):
    _, model = new_trees(seed, probe_iterations=2 if memory else None)
    from sklearn.utils._openmp_helpers import _openmp_effective_n_threads
    from threadpoolctl import threadpool_limits

    with threadpool_limits(limits=8, user_api='openmp'):
        if _openmp_effective_n_threads() != 8:
            raise ValueError('eight-thread fitting is not effective')
        model.fit(features, target, sample_weight=weights)
    if _openmp_effective_n_threads() != 1 or torch.get_num_threads() != 1:
        raise ValueError('single-thread inference runtime was not restored')
    return model
