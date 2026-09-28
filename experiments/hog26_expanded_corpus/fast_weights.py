"""The existing weighting formula, with group indexing instead of whole-array scans."""

import numpy as np
from scalar_evaluation import EvaluationIndex


def fitting_weights(game_ids, progress, fit_mask):
    ids, fit = np.asarray(game_ids), np.asarray(fit_mask, dtype=bool)
    index = EvaluationIndex(ids, progress)
    if fit.shape != ids.shape:
        raise ValueError("fitting mask shape differs")
    groups = index.group_ids
    counts = np.bincount(groups, minlength=index.group_count)
    fitting_counts = np.bincount(groups[fit], minlength=index.group_count)
    total_games = counts.reshape(-1, 3).sum(1)
    fitting_games = fitting_counts.reshape(-1, 3).sum(1)
    if not np.all((fitting_games == 0) | (fitting_games == total_games)):
        raise ValueError("fitting membership changes inside a game")
    game_count = int(np.count_nonzero(fitting_games))
    if game_count == 0:
        raise ValueError("no fitting games")
    reached = (counts.reshape(-1, 3) > 0).sum(1)
    denominator = game_count * np.repeat(reached, 3) * counts
    base = np.zeros(len(ids), dtype=np.float64)
    base[fit] = 1.0 / denominator[groups[fit]]
    margin = base.copy()
    phases = np.unique(index.phases[fit])
    for phase in phases:
        selected = fit & (index.phases == phase)
        margin[selected] /= len(phases) * margin[selected].sum()
    order = np.arange(len(ids)) if np.all(groups[1:] >= groups[:-1]) else np.argsort(groups, kind="stable")
    ordered_groups = groups[order]
    starts = np.r_[0, np.flatnonzero(np.diff(ordered_groups)) + 1]
    ends = np.r_[starts[1:], len(ids)]
    for start, end in zip(starts, ends, strict=True):
        positions = order[start:end]
        if not fit[positions[0]]:
            continue
        mass = margin[positions].sum()
        margin[positions] *= .5
        margin[positions[index.representative_mask[positions]]] += .5 * mass
    return base, margin
