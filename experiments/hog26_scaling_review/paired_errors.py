"""Paired error changes on identical diagnostic scenarios, never acceptance."""

import numpy as np


def paired_error_intervals(old_probability, new_probability, old_margin, new_margin,
                           labels, terminal_margin, weights, clusters,
                           *, replicates=2000, seed=1279511):
    """Positive values mean scaled-model improvement with the same row weights."""
    old_probability, new_probability = (
        np.asarray(x, dtype=np.float64) for x in (old_probability, new_probability)
    )
    old_margin, new_margin, terminal_margin, weights = (
        np.asarray(x, dtype=np.float64)
        for x in (old_margin, new_margin, terminal_margin, weights)
    )
    labels, clusters = np.asarray(labels), np.asarray(clusters)
    n = len(weights)
    if (old_probability.shape != (n, 3) or new_probability.shape != (n, 3)
            or any(x.shape != (n,) for x in
                   (old_margin, new_margin, terminal_margin, labels, clusters))):
        raise ValueError("paired rows must have identical shapes")
    if (not np.isin(labels, [0, 1, 2]).all()
            or not np.issubdtype(labels.dtype, np.integer)
            or not isinstance(replicates, int) or replicates <= 0
            or not np.isfinite(weights).all() or (weights < 0).any()):
        raise ValueError("invalid labels, weights, or replicate count")
    for probability in (old_probability, new_probability):
        if (not np.isfinite(probability).all() or (probability < 0).any()
                or not np.allclose(probability.sum(1), 1, atol=1e-6)):
            raise ValueError("invalid probabilities")
    if not all(np.isfinite(x).all() for x in (old_margin, new_margin, terminal_margin)):
        raise ValueError("nonfinite margins")
    active = weights > 0
    if not active.any():
        return {"status": "inconclusive-empty"}
    selected = np.flatnonzero(active)
    classes = labels[active]
    old_p, new_p = old_probability[selected], new_probability[selected]
    rows = np.arange(len(selected))
    onehot = np.eye(3)[classes]
    reductions = {
        "nll_reduction": np.log(np.maximum(new_p[rows, classes], 1e-12))
                         - np.log(np.maximum(old_p[rows, classes], 1e-12)),
        "margin_mae_reduction": np.abs(old_margin[active] - terminal_margin[active])
                                - np.abs(new_margin[active] - terminal_margin[active]),
        "brier_reduction": ((old_p - onehot) ** 2).sum(1) - ((new_p - onehot) ** 2).sum(1),
    }
    unique, inverse = np.unique(clusters[active], return_inverse=True)
    w = weights[active]
    mass = np.bincount(inverse, weights=w, minlength=len(unique))
    counts = np.random.default_rng(seed).multinomial(
        len(unique), np.full(len(unique), 1 / len(unique)), size=replicates
    )
    denominators = counts @ mass
    output = {}
    for name, values in reductions.items():
        totals = np.bincount(inverse, weights=w * values, minlength=len(unique))
        draws = counts @ totals / denominators
        output[name] = {
            "point": float(totals.sum() / mass.sum()),
            "lower_95": float(np.quantile(draws, 0.025)),
            "upper_95": float(np.quantile(draws, 0.975)),
        }
    return {
        "metrics": output, "scenario_clusters": len(unique),
        "replicates": replicates, "seed": seed,
        "scope": "Paired scenario-cluster bootstrap on opened diagnostic data; positive means improvement.",
        "status": "diagnostic" if len(unique) >= 2 else "inconclusive-single-cluster",
        "acceptance": False,
    }
