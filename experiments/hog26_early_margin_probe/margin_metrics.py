"""Absolute margin errors and paired scenario intervals for a focused assay."""

import numpy as np


def score(target, prediction):
    if target.shape != prediction.shape or not np.isfinite(prediction).all():
        raise ValueError('aligned finite margin predictions required')
    return float(np.abs(prediction - target).mean())


def paired(target, before, after, clusters):
    if not len(target) or any(value.shape != target.shape for value in (before, after, clusters)):
        raise ValueError('nonempty aligned paired margin rows required')
    change = np.abs(before - target) - np.abs(after - target)
    if not np.isfinite(change).all():
        raise ValueError('finite paired margin changes required')
    unique, inverse = np.unique(clusters, return_inverse=True)
    counts = np.random.default_rng(1280511).multinomial(len(unique), np.full(len(unique), 1 / len(unique)), size=2000)
    mass = np.bincount(inverse, minlength=len(unique))
    totals = np.bincount(inverse, weights=change, minlength=len(unique))
    draws = counts @ totals / (counts @ mass)
    return {'point': float(change.mean()), 'lower_95': float(np.quantile(draws, .025)),
            'upper_95': float(np.quantile(draws, .975)), 'clusters': len(unique), 'replicates': 2000, 'seed': 1280511}
