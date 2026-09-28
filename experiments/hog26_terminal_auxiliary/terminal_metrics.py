"""Bernoulli diagnostics with the unchanged game/phase evaluation distributions."""

import numpy as np
from scalar_evaluation import EvaluationIndex, evaluation_weights, slice_masks


def binary_auc(probability, labels, weights):
    order = np.argsort(probability, kind="stable")
    p, y, w = probability[order], labels[order], weights[order]
    positive, negative = w * y, w * (1 - y)
    if positive.sum() == 0 or negative.sum() == 0:
        return None
    starts = np.r_[0, np.flatnonzero(np.diff(p)) + 1]
    pos, neg = np.add.reduceat(positive, starts), np.add.reduceat(negative, starts)
    return float(np.sum(pos * (np.cumsum(neg) - .5 * neg)) / (pos.sum() * neg.sum()))


def measure(probability, labels, prior, weights, clusters, *, intervals):
    active = weights > 0
    if not active.any():
        return {"status": "inconclusive-empty"}
    p, y, q, w, c = [np.asarray(x)[active] for x in (probability, labels, prior, weights, clusters)]
    w = w / w.sum()
    p, q = np.clip(p, 1e-12, 1 - 1e-12), np.clip(q, 1e-12, 1 - 1e-12)
    nll = -(y * np.log(p) + (1 - y) * np.log1p(-p))
    baseline = -(y * np.log(q) + (1 - y) * np.log1p(-q))
    quantities = {"nll": nll, "prior_nll": baseline, "nll_gain": baseline - nll,
                  "brier": (p - y) ** 2, "predicted_mass": p, "observed_mass": y}
    result = {"rows": len(p), "clusters": len(np.unique(c)),
              "positive_clusters": len(np.unique(c[y == 1])),
              "negative_clusters": len(np.unique(c[y == 0])),
              "metrics": {name: float(np.sum(w * value)) for name, value in quantities.items()}}
    result["metrics"]["auc"] = binary_auc(p, y, w)
    bins = np.minimum((p * 10).astype(int), 9)
    result["metrics"]["ece"] = float(sum(abs(np.sum(w[bins == b] * (p[bins == b] - y[bins == b]))) for b in range(10)))
    if intervals:
        unique, inverse = np.unique(c, return_inverse=True)
        mass = np.bincount(inverse, weights=w)
        counts = np.random.default_rng(1279511).multinomial(len(unique), np.full(len(unique), 1 / len(unique)), size=2000)
        denominator = counts @ mass
        result["intervals"] = {}
        for name, value in quantities.items():
            total = np.bincount(inverse, weights=w * value)
            draws = counts @ total / denominator
            result["intervals"][name] = {"lower_95": float(np.quantile(draws, .025)),
                                          "upper_95": float(np.quantile(draws, .975))}
    return result


def report(evaluation, labels, probability, prior, mask=None, *, intervals=False):
    ids, progress, _, _, _, seats, styles, folds, clusters, families = evaluation
    prior = np.broadcast_to(prior, labels.shape)
    if (probability.shape != labels.shape or not np.isin(labels, [0, 1]).all()
            or not np.isfinite(probability).all() or not np.isfinite(prior).all()
            or ((probability < 0) | (probability > 1)).any() or ((prior <= 0) | (prior >= 1)).any()):
        raise ValueError("invalid auxiliary reporting arrays")
    selected = np.ones(len(ids), dtype=bool) if mask is None else mask
    masks = slice_masks(progress, seats, styles, folds)
    masks.update({f"family/{f}": families == f for f in np.unique(families)})
    index = EvaluationIndex(ids, progress)
    result = {}
    for representative, name in ((False, "all_states"), (True, "representatives")):
        result[name] = {key: measure(probability, labels, prior,
                                    evaluation_weights(ids, progress, value & selected,
                                                       representative=representative, index=index),
                                    clusters, intervals=intervals)
                        for key, value in masks.items()}
    return result
