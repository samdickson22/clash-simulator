"""Auxiliary bridge-style scores and paired whole-scenario uncertainty."""

import numpy as np


def losses(labels, probability):
    y, p = np.asarray(labels), np.asarray(probability, dtype=np.float64)
    if (y.ndim != 1 or not len(y) or y.shape != p.shape or not np.isin(y, (0, 1)).all() or not np.isfinite(p).all()
            or ((p < 0) | (p > 1)).any()):
        raise ValueError('valid binary auxiliary probabilities and labels required')
    logloss = -np.where(y == 1, np.log(np.maximum(p, 1e-12)), np.log(np.maximum(1 - p, 1e-12)))
    return {'nll': logloss, 'brier': np.square(p - y)}


def scores(labels, probability, prior):
    from sklearn.metrics import roc_auc_score

    values = losses(labels, probability)
    reference = losses(labels, np.full(len(labels), prior))
    return {'games': len(labels), 'bridge_games': int(np.sum(labels)), 'bridge_rate': float(np.mean(labels)),
            'mean_probability': float(np.mean(probability)), 'nll': float(values['nll'].mean()),
            'nll_gain_over_fitting_prior': float((reference['nll'] - values['nll']).mean()),
            'binary_brier': float(values['brier'].mean()),
            'bridge_auc': float(roc_auc_score(labels, probability)) if len(np.unique(labels)) == 2 else None,
            'accuracy_at_half': float(np.mean((probability >= .5) == labels))}


def paired_scores(labels, base_probability, history_probability, clusters):
    before, after = losses(labels, base_probability), losses(labels, history_probability)
    unique, inverse = np.unique(clusters, return_inverse=True)
    counts = np.random.default_rng(1280411).multinomial(len(unique), np.full(len(unique), 1 / len(unique)), size=2000)
    mass = np.bincount(inverse, minlength=len(unique))
    denominator = counts @ mass
    result = {}
    for name in ('nll', 'brier'):
        change = before[name] - after[name]
        totals = np.bincount(inverse, weights=change, minlength=len(unique))
        draws = counts @ totals / denominator
        result[name + '_reduction'] = {'point': float(change.mean()), 'lower_95': float(np.quantile(draws, .025)),
                                       'upper_95': float(np.quantile(draws, .975))}
    return {'scenario_clusters': len(unique), 'replicates': 2000, 'seed': 1280411, 'metrics': result,
            'scope': 'Paired bridge-style classification on identical held-family training representatives; positive means history improves the auxiliary score.'}
