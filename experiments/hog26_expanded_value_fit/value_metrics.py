"""Unchanged slice definitions, scoring, and whole-scenario uncertainty."""

import numpy as np
from scalar_evaluation import (
    EvaluationIndex,
    cluster_bootstrap,
    coverage,
    evaluation_weights,
    metrics,
    slice_masks,
)


def report_predictions(public, probabilities, margin, prior, *, fit_mask=None, bootstrap=False, log=None):
    ids, progress, labels, target, current, seats, styles, folds, clusters, families = public
    slices = slice_masks(progress, seats, styles, folds)
    slices.update({f'family/{family}': families == family for family in np.unique(families)})
    index = EvaluationIndex(ids, progress)
    results = {}
    for representative, distribution in ((False, 'all_states'), (True, 'representatives')):
        group = {}
        for name, mask in slices.items():
            if fit_mask is not None:
                mask = mask & fit_mask
            weights = evaluation_weights(ids, progress, mask, representative=representative, index=index)
            if not weights.any():
                group[name] = {'status': 'inconclusive-empty'}
                continue
            args = (probabilities, labels, margin, target, current, weights, prior)
            value = {'coverage': coverage(ids, labels, clusters, weights), 'metrics': metrics(*args)}
            if bootstrap:
                value['intervals'] = cluster_bootstrap(*args, clusters, replicates=2000, seed=1279511)
            group[name] = value
            if log:
                log({'distribution': distribution, 'slice': name})
        results[distribution] = group
    return results
