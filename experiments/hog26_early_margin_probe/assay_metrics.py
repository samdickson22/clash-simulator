"""Retain all fixed early-point groups for the focused diagnostic."""

import numpy as np
from margin_metrics import score


def masks(data):
    result = {'overall': np.ones(6144, dtype=bool), 'seat/0': data.seats == 0, 'seat/1': data.seats == 1}
    for style in np.unique(data.styles):
        result[f'style/{style}'] = data.styles == style
        for seat in (0, 1):
            result[f'style/{style}/seat/{seat}'] = (data.styles == style) & (data.seats == seat)
    result.update({f'family/{family}': data.families == family for family in np.unique(data.families)})
    return result


def report(data, prediction, selection):
    result = {}
    for name, mask in masks(data).items():
        chosen = mask & selection
        if not chosen.any():
            result[name] = {'status': 'empty'}
            continue
        baseline = score(data.target[chosen], data.current[chosen])
        error = score(data.target[chosen], prediction[chosen])
        result[name] = {'games': int(chosen.sum()), 'clusters': len(np.unique(data.clusters[chosen])),
                        'baseline_mae': baseline, 'model_mae': error, 'margin_gain': baseline - error}
    return result
