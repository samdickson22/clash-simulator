"""Synthetic-tested pilot weights and diagnostics. Model class order is L, D, W.

Metadata and terminal labels are evaluation-only. Scenario IDs must come from
an independent corpus/deal audit; this module does not infer independence.
"""

from __future__ import annotations

import numpy as np

FAMILY_FOLDS = tuple(
    tuple(f"family-{n:03d}" for n in pair) for pair in ((0, 1), (2, 3), (4, 5), (6, 7))
)
PHASE_NAMES = ("early", "middle", "late")
CLASS_NAMES = ("loss", "draw", "win")


def raw_wdl_to_class_index(raw_wdl):
    """Convert writer one-hot W,D,L to model class indices L=0,D=1,W=2."""
    raw = np.asarray(raw_wdl)
    if (
        raw.ndim < 1
        or raw.shape[-1] != 3
        or not np.isin(raw, [0, 1]).all()
        or not (raw.sum(axis=-1) == 1).all()
    ):
        raise ValueError("expected exact writer W,D,L one-hot labels")
    return 2 - raw.argmax(axis=-1)


def phase_ids(progress):
    progress = np.asarray(progress, dtype=np.float64)
    if progress.ndim != 1 or not np.isfinite(progress).all() or (progress < 0).any():
        raise ValueError("progress must be a finite nonnegative vector")
    return np.searchsorted([1 / 3, 2 / 3], progress, side="right")


def _same_length(*arrays):
    if len({len(a) for a in arrays}) != 1:
        raise ValueError("row arrays have different lengths")


def _constant_per_game(game_ids, values, description):
    _, first, inverse = np.unique(game_ids, return_index=True, return_inverse=True)
    if not np.array_equal(values, values[first[inverse]]):
        raise ValueError(f"{description} changes inside a game")


def fold_masks(game_ids, families, fold):
    game_ids, families = np.asarray(game_ids), np.asarray(families)
    _same_length(game_ids, families)
    if fold not in range(4):
        raise ValueError("fold must be 0..3")
    if not np.isin(families, sum(FAMILY_FOLDS, ())).all():
        raise ValueError("non-training family supplied")
    _constant_per_game(game_ids, families, "family")
    excluded = np.isin(families, FAMILY_FOLDS[fold])
    if not excluded.any() or excluded.all():
        raise ValueError("fold requires fitting and excluded games")
    return ~excluded, excluded


class EvaluationIndex:
    """Immutable game/phase grouping reusable across report slices.

    Contains only public progress and evaluation game identifiers. All returned
    arrays are copies or newly allocated; caller mutation cannot alter indexing.
    """

    def __init__(self, game_ids, progress):
        self.game_ids = np.array(game_ids, copy=True)
        self.progress = np.array(progress, dtype=np.float64, copy=True)
        self.phases = phase_ids(self.progress)
        _same_length(self.game_ids, self.progress)
        if self.game_ids.ndim != 1:
            raise ValueError("game IDs must be a vector")
        games, inverse = np.unique(self.game_ids, return_inverse=True)
        self.group_ids = inverse * 3 + self.phases
        self.group_count = len(games) * 3
        distances = np.abs(self.progress - np.array([1 / 6, 1 / 2, 5 / 6])[self.phases])
        minimum = np.full(self.group_count, np.inf)
        np.minimum.at(minimum, self.group_ids, distances)
        rows = np.arange(len(self.progress))
        nearest = distances == minimum[self.group_ids]
        first = np.full(self.group_count, len(rows), dtype=np.int64)
        np.minimum.at(first, self.group_ids[nearest], rows[nearest])
        self.representative_mask = np.zeros(len(rows), dtype=bool)
        self.representative_mask[first[first < len(rows)]] = True
        for value in vars(self).values():
            if isinstance(value, np.ndarray):
                value.flags.writeable = False

    def validate(self, game_ids, progress):
        if not np.array_equal(game_ids, self.game_ids) or not np.array_equal(
            progress, self.progress
        ):
            raise ValueError("evaluation index does not match supplied rows/progress")


def representatives(game_ids, progress, *, index=None):
    """Boolean nearest-center mask; incoming row order breaks exact ties."""
    if index is None:
        index = EvaluationIndex(game_ids, progress)
    else:
        index.validate(game_ids, progress)
    return index.representative_mask.copy()


def fitting_weights(game_ids, progress, fit_mask):
    """Return unit-sum WDL and phase-balanced 50/50 uniform/rep margin mass.

    Excluded rows get exactly zero. The mean positive-support row weight is
    1/n_fit_rows for a uniform-row sampler. A uniform-game sampler instead
    multiplies summed per-game losses by n_fit_games / batch_games, with no
    realized weight normalization. This preserves the full objective.
    """
    game_ids, fit_mask = np.asarray(game_ids), np.asarray(fit_mask, dtype=bool)
    phases = phase_ids(progress)
    _same_length(game_ids, phases, fit_mask)
    _constant_per_game(game_ids, fit_mask, "fitting membership")
    games = np.unique(game_ids[fit_mask])
    if not len(games):
        raise ValueError("no fitting games")
    base = np.zeros(len(game_ids), dtype=np.float64)
    rep = representatives(game_ids, progress)
    for game in games:
        reached = np.unique(phases[game_ids == game])
        for phase in reached:
            rows = (game_ids == game) & (phases == phase)
            base[rows] = 1 / (len(games) * len(reached) * rows.sum())
    margin = base.copy()
    reached_phases = np.unique(phases[fit_mask])
    for phase in reached_phases:
        rows = fit_mask & (phases == phase)
        margin[rows] /= len(reached_phases) * margin[rows].sum()
    for game in games:
        for phase in np.unique(phases[game_ids == game]):
            rows = (game_ids == game) & (phases == phase)
            mass = margin[rows].sum()
            margin[rows] *= 0.5
            margin[rows & rep] += 0.5 * mass
    return base, margin


def evaluation_weights(
    game_ids, progress, mask=None, *, representative=False, index=None
):
    """Equal game mass within each phase, then equal reached-phase mass.

    Recompute on the requested slice, not on fitting weights. Representatives
    are selected on the original complete games before any slice filtering.
    Pass a precomputed EvaluationIndex to reuse grouping for repeated slices.
    """
    if index is None:
        index = EvaluationIndex(game_ids, progress)
    else:
        index.validate(game_ids, progress)
    n = len(index.phases)
    mask = np.ones(n, bool) if mask is None else np.asarray(mask, bool)
    if mask.shape != (n,):
        raise ValueError("slice mask must match evaluation rows")
    if representative:
        mask = mask & index.representative_mask
    result = np.zeros(n, dtype=np.float64)
    if not mask.any():
        return result
    counts = np.bincount(index.group_ids[mask], minlength=index.group_count)
    games_per_phase = (counts.reshape(-1, 3) > 0).sum(axis=0)
    reached_phase_count = np.count_nonzero(games_per_phase)
    result[mask] = 1 / (
        reached_phase_count
        * games_per_phase[index.phases[mask]]
        * counts[index.group_ids[mask]]
    )
    return result


def empirical_prior(game_ids, class_indices, fit_mask):
    game_ids, labels, fit_mask = (
        np.asarray(game_ids),
        np.asarray(class_indices),
        np.asarray(fit_mask, bool),
    )
    _same_length(game_ids, labels, fit_mask)
    _validate_labels(labels)
    _constant_per_game(game_ids, labels, "terminal label")
    _constant_per_game(game_ids, fit_mask, "fitting membership")
    games, first = np.unique(game_ids[fit_mask], return_index=True)
    if not len(games):
        raise ValueError("no fitting games")
    return np.bincount(labels[fit_mask][first], minlength=3) / len(games)


def _validate_labels(labels):
    if (
        labels.ndim != 1
        or labels.dtype.kind not in "iu"
        or not np.isin(labels, [0, 1, 2]).all()
    ):
        raise ValueError("labels must be integer class indices L=0,D=1,W=2")


def _ece(prob, success, weights):
    bins = np.minimum((prob * 10).astype(int), 9)
    return float(
        sum(
            abs(np.sum(weights[bins == b] * (prob[bins == b] - success[bins == b])))
            for b in range(10)
        )
    )


def _auc(probabilities, labels, weights):
    decisive = labels != 1
    score = probabilities[:, 2] / np.maximum(
        probabilities[:, 0] + probabilities[:, 2], 1e-12
    )
    order = np.argsort(score[decisive], kind="stable")
    scores, positive, w = (
        score[decisive][order],
        (labels[decisive] == 2)[order],
        weights[decisive][order],
    )
    wp, wn = w * positive, w * ~positive
    if wp.sum() == 0 or wn.sum() == 0:
        return None
    starts = np.r_[0, np.flatnonzero(np.diff(scores)) + 1]
    p, n = np.add.reduceat(wp, starts), np.add.reduceat(wn, starts)
    return float(np.sum(p * (np.cumsum(n) - 0.5 * n)) / (p.sum() * n.sum()))


def metrics(
    probabilities,
    class_indices,
    margin_prediction,
    terminal_margin,
    current_margin,
    weights,
    prior,
):
    """Weighted point estimates. Probabilities/prior columns are L,D,W."""
    p, labels = np.asarray(probabilities, np.float64), np.asarray(class_indices)
    predicted, target, baseline, w = (
        np.asarray(a, np.float64)
        for a in (margin_prediction, terminal_margin, current_margin, weights)
    )
    _validate_labels(labels)
    _same_length(p, labels, predicted, target, baseline, w)
    if (
        p.shape != (len(labels), 3)
        or not np.isfinite(p).all()
        or (p < 0).any()
        or not np.allclose(p.sum(axis=1), 1, atol=1e-6)
    ):
        raise ValueError("invalid L,D,W probabilities")
    if (
        any(
            a.ndim != 1 or not np.isfinite(a).all()
            for a in (predicted, target, baseline, w)
        )
        or (w < 0).any()
        or w.sum() <= 0
    ):
        raise ValueError("invalid margins/weights or empty evaluation")
    prior = np.asarray(prior, np.float64)
    if prior.shape == (3,):
        prior = np.broadcast_to(prior, p.shape)
    if (
        prior.shape != p.shape
        or not np.isfinite(prior).all()
        or (prior < 0).any()
        or not np.allclose(prior.sum(axis=1), 1)
    ):
        raise ValueError(
            "invalid fitting-only prior; OOF supports row-aligned fold priors"
        )
    w = w / w.sum()
    onehot = np.eye(3)[labels]
    nll = -np.log(np.maximum(p[np.arange(len(labels)), labels], 1e-12))
    prior_nll = -np.log(np.maximum(prior[np.arange(len(labels)), labels], 1e-12))
    error, baseline_error = np.abs(predicted - target), np.abs(baseline - target)
    result = {
        "nll": float(w @ nll),
        "prior_nll": float(w @ prior_nll),
        "nll_gain": float(w @ (prior_nll - nll)),
        "brier": float(w @ np.sum((p - onehot) ** 2, axis=1)),
        "top_label_ece": _ece(p.max(axis=1), (p.argmax(axis=1) == labels), w),
        "decisive_auc": _auc(p, labels, w),
        "margin_mae": float(w @ error),
        "baseline_margin_mae": float(w @ baseline_error),
        "margin_gain": float(w @ (baseline_error - error)),
    }
    for i, name in enumerate(CLASS_NAMES):
        result[f"ece_{name}"] = _ece(p[:, i], labels == i, w)
        result[f"predicted_mass_{name}"] = float(w @ p[:, i])
        result[f"observed_mass_{name}"] = float(w @ (labels == i))
    return result


def cluster_bootstrap(
    probabilities,
    class_indices,
    margin_prediction,
    terminal_margin,
    current_margin,
    weights,
    prior,
    cluster_ids,
    *,
    replicates=2000,
    seed=1279511,
):
    """Percentile intervals resample whole audited scenarios, including both seats.

    Fixed evaluation row mass is multiplied by each sampled cluster's count;
    resulting ratios are normalized within each replicate. Undefined AUC draws
    are counted and reported, never silently converted into passing evidence.
    """
    weights, cluster_ids = np.asarray(weights, np.float64), np.asarray(cluster_ids)
    _same_length(weights, cluster_ids)
    if not isinstance(replicates, int) or replicates <= 0:
        raise ValueError("replicates must be positive")
    active = weights > 0
    clusters, inverse = np.unique(cluster_ids[active], return_inverse=True)
    if not len(clusters):
        raise ValueError("no positive-mass scenario clusters")
    args = [
        np.asarray(a)[active]
        for a in (
            probabilities,
            class_indices,
            margin_prediction,
            terminal_margin,
            current_margin,
        )
    ]
    prior = np.asarray(prior)
    if prior.ndim == 2:
        prior = prior[active]
    point = metrics(*args, weights[active], prior)
    p, labels, predicted, target, baseline = args
    w = weights[active]
    prior_rows = np.broadcast_to(prior, p.shape) if prior.ndim == 1 else prior
    onehot = np.eye(3)[labels]
    nll = -np.log(np.maximum(p[np.arange(len(labels)), labels], 1e-12))
    prior_nll = -np.log(np.maximum(prior_rows[np.arange(len(labels)), labels], 1e-12))
    error, baseline_error = np.abs(predicted - target), np.abs(baseline - target)
    row_values = {
        "nll": nll,
        "prior_nll": prior_nll,
        "nll_gain": prior_nll - nll,
        "brier": np.sum((p - onehot) ** 2, axis=1),
        "margin_mae": error,
        "baseline_margin_mae": baseline_error,
        "margin_gain": baseline_error - error,
    }
    for i, name in enumerate(CLASS_NAMES):
        row_values[f"predicted_mass_{name}"] = p[:, i]
        row_values[f"observed_mass_{name}"] = labels == i
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(
        len(clusters), np.full(len(clusters), 1 / len(clusters)), size=replicates
    )
    cluster_mass = np.bincount(inverse, weights=w, minlength=len(clusters))
    denominators = counts @ cluster_mass
    values = {}
    for key, rows in row_values.items():
        totals = np.bincount(inverse, weights=w * rows, minlength=len(clusters))
        values[key] = (counts @ totals / denominators).tolist()
    calibration = [("top_label_ece", p.max(axis=1), p.argmax(axis=1) == labels)]
    calibration += [
        (f"ece_{name}", p[:, i], labels == i) for i, name in enumerate(CLASS_NAMES)
    ]
    for key, confidence, correct in calibration:
        bins = np.minimum((confidence * 10).astype(int), 9)
        cluster_bins = np.bincount(
            inverse * 10 + bins,
            weights=w * (confidence - correct),
            minlength=len(clusters) * 10,
        ).reshape(len(clusters), 10)
        values[key] = (
            np.abs(counts @ cluster_bins).sum(axis=1) / denominators
        ).tolist()
    # AUC is not additive. Sort once, then recompute tied-score weighted ranks
    # for each cluster draw without sorting or revalidating the full row set.
    decisive = labels != 1
    scores = p[:, 2] / np.maximum(p[:, 0] + p[:, 2], 1e-12)
    order = np.argsort(scores[decisive], kind="stable")
    scores, positive = scores[decisive][order], (labels[decisive] == 2)[order]
    dw, dc = w[decisive][order], inverse[decisive][order]
    starts = np.r_[0, np.flatnonzero(np.diff(scores)) + 1]
    values["decisive_auc"] = []
    if len(scores):
        for draw in counts:
            sample_w = dw * draw[dc]
            pw, nw = sample_w * positive, sample_w * ~positive
            if pw.sum() == 0 or nw.sum() == 0:
                continue
            pp, nn = np.add.reduceat(pw, starts), np.add.reduceat(nw, starts)
            values["decisive_auc"].append(
                float(np.sum(pp * (np.cumsum(nn) - 0.5 * nn)) / (pp.sum() * nn.sum()))
            )
    intervals = {}
    for key, vals in values.items():
        intervals[key] = {
            "lower_95": float(np.quantile(vals, 0.025)) if vals else None,
            "upper_95": float(np.quantile(vals, 0.975)) if vals else None,
            "defined_replicates": len(vals),
            "undefined_replicates": replicates - len(vals),
        }
    return {
        "point": point,
        "intervals": intervals,
        "scenario_clusters": len(clusters),
        "replicates": replicates,
        "seed": seed,
        "interval_scope": "diagnostic only; fewer than two clusters is insufficient"
        if len(clusters) < 2
        else "scenario-cluster percentile bootstrap",
    }


def coverage(game_ids, class_indices, cluster_ids, weights):
    games, labels, clusters, weights = map(
        np.asarray, (game_ids, class_indices, cluster_ids, weights)
    )
    _same_length(games, labels, clusters, weights)
    _validate_labels(labels)
    _constant_per_game(games, labels, "terminal label")
    _constant_per_game(games, clusters, "scenario cluster")
    active = weights > 0
    return {
        "games": len(np.unique(games[active])),
        "decision_rows": int(active.sum()),
        "scenario_clusters": len(np.unique(clusters[active])),
        "clusters_containing_loss": len(np.unique(clusters[active & (labels == 0)])),
        "clusters_containing_win": len(np.unique(clusters[active & (labels == 2)])),
        "natural_draw_games": len(np.unique(games[active & (labels == 1)])),
    }


def slice_masks(progress, seats, styles, folds):
    """All predeclared marginal and phase/seat/style slices; retain empty cells."""
    phases, seats, styles, folds = (
        phase_ids(progress),
        np.asarray(seats),
        np.asarray(styles),
        np.asarray(folds),
    )
    _same_length(phases, seats, styles, folds)
    result = {"overall": np.ones(len(phases), bool)}
    for fold in range(4):
        result[f"fold/{fold}"] = folds == fold
    declared_styles = (
        "balanced",
        "random",
        "bridge-pressure",
        "reactive-defense",
        "slow-push",
        "spell-control",
    )
    for phase, name in enumerate(PHASE_NAMES):
        result[f"phase/{name}"] = phases == phase
        for seat in (0, 1):
            for style in declared_styles:
                result[f"phase/{name}/seat/{seat}/style/{style}"] = (
                    (phases == phase) & (seats == seat) & (styles == style)
                )
    for seat in (0, 1):
        result[f"seat/{seat}"] = seats == seat
    for style in declared_styles:
        result[f"style/{style}"] = styles == style
    return result
