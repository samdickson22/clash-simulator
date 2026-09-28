"""Reuse byte-identical WDL bootstrap statistics; recompute both margin intervals."""

from copy import deepcopy

import numpy as np
from scalar_evaluation import metrics


def reuse_wdl_bootstrap(probability, reference_probability, labels, margin, target, current,
                        weights, prior, clusters, reference, *, replicates=2000, seed=1279511):
    if (probability.shape != reference_probability.shape or probability.dtype != reference_probability.dtype
            or probability.tobytes() != reference_probability.tobytes()):
        raise ValueError('byte-identical WDL probabilities required for reuse')
    active = np.asarray(weights) > 0
    if not active.any():
        raise ValueError('positive evaluation mass required')
    selected_prior = prior[active] if np.asarray(prior).ndim == 2 else prior
    args = [np.asarray(value)[active] for value in (probability, labels, margin, target, current)]
    w = np.asarray(weights, dtype=np.float64)[active]
    point = metrics(*args, w, selected_prior)
    if any(value != reference['point'][name] for name, value in point.items() if name not in ('margin_mae', 'margin_gain')):
        raise ValueError('unchanged WDL/baseline statistics or evaluation inputs differ')
    unique, inverse = np.unique(np.asarray(clusters)[active], return_inverse=True)
    if reference['replicates'] != replicates or reference['seed'] != seed or reference['scenario_clusters'] != len(unique):
        raise ValueError('bootstrap design differs from reviewed reference')
    counts = np.random.default_rng(seed).multinomial(len(unique), np.full(len(unique), 1 / len(unique)), size=replicates)
    mass = np.bincount(inverse, weights=w, minlength=len(unique))
    denominator = counts @ mass
    error = np.abs(args[2] - args[3])
    baseline_error = np.abs(args[4] - args[3])
    result = deepcopy(reference)
    result['point'] = point
    for name, rows in (('margin_mae', error), ('margin_gain', baseline_error - error)):
        totals = np.bincount(inverse, weights=w * rows, minlength=len(unique))
        draws = counts @ totals / denominator
        result['intervals'][name] = {'lower_95': float(np.quantile(draws, .025)), 'upper_95': float(np.quantile(draws, .975)),
                                     'defined_replicates': replicates, 'undefined_replicates': 0}
    return result
