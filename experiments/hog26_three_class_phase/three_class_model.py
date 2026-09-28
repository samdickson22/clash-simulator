"""Fixed phase classifier settings with explicit absent-class recording."""

import torch
from value_models import new_trees


def fit_classifier(features, labels, weights, seed, *, memory=False):
    model, _ = new_trees(seed, probe_iterations=2 if memory else None)
    from sklearn.utils._openmp_helpers import _openmp_effective_n_threads
    from threadpoolctl import threadpool_limits

    with threadpool_limits(limits=8, user_api='openmp'):
        if _openmp_effective_n_threads() != 8:
            raise ValueError('eight fitting threads required')
        model.fit(features, labels, sample_weight=weights)
    if _openmp_effective_n_threads() != 1 or torch.get_num_threads() != 1:
        raise ValueError('single-thread inference runtime not restored')
    return model
