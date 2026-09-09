"""Natural-game acceptance by phase, seat and opponent, with cluster coverage."""

from __future__ import annotations

from itertools import product
from typing import Any

import numpy as np
import torch

from scripts.hog26_scenario_clusters import episode_matchup_cluster


def weighted_binary_auc(labels, scores, weights):
    labels = np.asarray(labels, dtype=bool)
    _, groups = np.unique(scores, return_inverse=True)
    positive = np.bincount(groups, weights=np.asarray(weights) * labels)
    negative = np.bincount(groups, weights=np.asarray(weights) * ~labels)
    denominator = positive.sum() * negative.sum()
    if denominator <= 0:
        return None
    below = np.cumsum(negative) - negative
    return float((positive * (below + 0.5 * negative)).sum() / denominator)


def weighted_outcome_metrics(probabilities, outcomes, weights):
    p = np.asarray(probabilities, dtype=np.float64)
    y = np.asarray(outcomes)
    w = np.asarray(weights, dtype=np.float64)
    if (
        p.shape != (len(y), 3) or w.shape != y.shape or not len(y)
        or not np.isfinite(p).all() or (p < 0).any()
        or not np.allclose(p.sum(1), 1) or not np.isin(y, [-1, 0, 1]).all()
        or not np.isfinite(w).all() or (w <= 0).any()
    ):
        raise ValueError("invalid weighted outcome rows")
    w = w / w.sum()
    target = y.astype(int) + 1
    def calibration_error(probability, event):
        value = 0.0
        for index in range(10):
            mask = (probability >= index / 10) & (
                probability <= 1 if index == 9 else probability < (index + 1) / 10
            )
            value += abs(float((w[mask] * (probability[mask] - event[mask])).sum()))
        return value
    decisive = y != 0
    return {
        "nll": float(w @ -np.log(np.maximum(p[np.arange(len(y)), target], 1e-12))),
        "brier": float(w @ ((p - np.eye(3)[target]) ** 2).sum(1)),
        "ece_10": calibration_error(p.max(1), p.argmax(1) == target),
        "classwise_ece_10": {name: calibration_error(p[:, index], target == index)
                             for index, name in enumerate(("loss", "draw", "win"))},
        "decisive_auc": weighted_binary_auc(
            y[decisive] == 1, (p[:, 2] - p[:, 0])[decisive], w[decisive]
        ),
        "mean_probability": dict(zip(("loss", "draw", "win"), (w @ p).tolist(), strict=True)),
        "empirical_class_mass": {name: float(w[target == index].sum())
                                 for index, name in enumerate(("loss", "draw", "win"))},
    }


def clustered_mean_interval(values, clusters, *, replicates: int, seed: int):
    values = np.asarray(values, dtype=np.float64)
    _, ids = np.unique(clusters, return_inverse=True)
    if not len(ids):
        return None
    sums = np.bincount(ids, weights=values)
    counts = np.bincount(ids)
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(replicates):
        selected = rng.integers(0, len(counts), len(counts))
        estimates.append(sums[selected].sum() / counts[selected].sum())
    return {
        "point": float(values.mean()),
        "lower_95": float(np.quantile(estimates, 0.025)),
        "upper_95": float(np.quantile(estimates, 0.975)),
        "independent_clusters": len(counts),
        "replicates": replicates,
    }


def evaluate_slices(
    *,
    probabilities,
    predicted_margin,
    target_margin,
    outcomes,
    current_margin,
    phases,
    seats,
    styles,
    clusters,
    expected_styles,
    prior,
    gates,
    design,
    seed,
    include_joint=True,
) -> dict[str, Any]:
    from scripts.train_hog26_actor_outcome import _binary_auc, _ece

    p = np.asarray(probabilities, dtype=np.float64)
    y = np.asarray(outcomes)
    n = len(y)
    arrays = [
        predicted_margin,
        target_margin,
        current_margin,
        phases,
        seats,
        styles,
        clusters,
    ]
    if p.shape != (n, 3) or any(np.asarray(a).shape != (n,) for a in arrays):
        raise ValueError("slice evaluation rows are misaligned")
    if (
        not np.isfinite(p).all()
        or (p < 0).any()
        or not np.allclose(p.sum(1), 1)
        or not np.isin(y, [-1, 0, 1]).all()
        or not all(np.isfinite(a).all() for a in arrays[:3])
    ):
        raise ValueError("invalid public predictions or terminal labels")
    prior = np.asarray(prior, dtype=np.float64)
    if prior.shape != (3,) or (prior <= 0).any() or not np.isclose(prior.sum(), 1):
        raise ValueError("invalid training-only prior")
    predicted_margin, target_margin, current_margin, phases, seats, styles, clusters = (
        np.asarray(a) for a in arrays
    )
    if not set(styles).issubset(expected_styles):
        raise ValueError("unexpected opponent in natural acceptance data")
    label_ids = y.astype(int) + 1
    gain = np.abs(current_margin - target_margin) - np.abs(
        predicted_margin - target_margin
    )
    phase_names = ("early", "middle", "late")
    masks = [("overall", "overall", np.ones(n, dtype=bool))]
    masks += [(f"phase/{v}", "phase", phases == v) for v in phase_names]
    masks += [(f"seat/{v}", "seat", seats == v) for v in (0, 1)]
    masks += [(f"style/{v}", "style", styles == v) for v in expected_styles]
    if include_joint:
        masks += [
            (
                f"phase/{phase}/seat/{seat}/style/{style}",
                "joint",
                (phases == phase) & (seats == seat) & (styles == style),
            )
            for phase, seat, style in product(phase_names, (0, 1), expected_styles)
        ]
    reports = {}
    for index, (name, kind, mask) in enumerate(masks):
        rows = np.flatnonzero(mask)
        cluster_count = len(np.unique(clusters[rows]))
        by_outcome = {
            str(label): len(np.unique(clusters[rows][y[rows] == label]))
            for label in (-1, 0, 1)
        }
        coverage = cluster_count >= design[
            "minimum_independent_matchup_clusters_per_slice"
        ] and all(
            by_outcome[str(label)]
            >= design["minimum_clusters_with_each_decisive_outcome_per_slice"]
            for label in (-1, 1)
        )
        result = {
            "required": include_joint or kind == "overall",
            "rows": len(rows),
            "independent_clusters": cluster_count,
            "clusters_by_outcome": by_outcome,
            "coverage_passed": coverage,
            "metrics_passed": False,
            "passed": False,
        }
        if len(rows):
            decisive = y[rows] != 0
            auc = _binary_auc(
                torch.as_tensor(y[rows][decisive] == 1),
                torch.as_tensor((p[rows, 2] - p[rows, 0])[decisive]),
            )
            nll = float(-np.log(np.maximum(p[rows, label_ids[rows]], 1e-12)).mean())
            prior_nll = float(-np.log(prior[label_ids[rows]]).mean())
            ece = _ece(torch.as_tensor(p[rows]), torch.as_tensor(label_ids[rows]))
            mae = float(np.abs(predicted_margin[rows] - target_margin[rows]).mean())
            improvement = float(gain[rows].mean())
            aggregate = kind in {"overall", "seat", "style"}
            checks = {
                "ece": ece <= gates["maximum_ece"],
                "auc": auc is not None
                and auc
                >= gates[
                    "minimum_natural_auc" if aggregate else "minimum_natural_phase_auc"
                ],
                "margin": improvement
                >= (
                    gates["minimum_margin_mae_improvement"]
                    if aggregate
                    else -gates["maximum_phase_margin_mae_regression"]
                ),
            }
            if aggregate:
                checks.update(
                    nll=prior_nll - nll >= gates["minimum_nll_improvement"],
                    absolute_margin=mae <= gates["maximum_margin_mae"],
                )
            interval = None
            if kind == "phase":
                interval = clustered_mean_interval(
                    gain[rows],
                    clusters[rows],
                    replicates=gates["cluster_bootstrap_replicates"],
                    seed=seed + index,
                )
                phase_gate = design["phase_margin_learning_gate"]
                checks["learned_phase_margin"] = (
                    improvement >= phase_gate["minimum_mae_improvement"]
                    and interval["lower_95"]
                    >= phase_gate["minimum_cluster_bootstrap_lower_95_improvement"]
                )
            result.update(
                nll=nll,
                prior_nll=prior_nll,
                nll_improvement=prior_nll - nll,
                ece=float(ece),
                decisive_auc=auc,
                margin_mae=mae,
                margin_mae_improvement=improvement,
                margin_improvement_interval=interval,
                checks=checks,
                metrics_passed=all(checks.values()),
                passed=coverage and all(checks.values()),
            )
        reports[name] = result
    required = [r for r in reports.values() if r["required"]]
    return {
        "status": "passed"
        if all(r["passed"] for r in required)
        else (
            "inconclusive-reject"
            if any(not r["coverage_passed"] for r in required)
            else "rejected"
        ),
        "passed": all(r["passed"] for r in required),
        "slices": reports,
    }


@torch.no_grad()
def evaluate_loaded_public_slices(
    head, features, loaded, prior, protocol, *, stage, device, seed
):
    from scripts.train_hog26_actor_outcome import (
        _outcome_source,
        phase_balanced_matchup_clusters,
        phase_balanced_row_indices,
    )

    rows = phase_balanced_row_indices(loaded).numpy()
    columns = {
        name: []
        for name in ("outcomes", "margins", "seats", "styles", "decks", "natural")
    }
    for metadata, corpus in loaded:
        lengths = np.diff(corpus.episode_offsets)
        episode = corpus.episode_arrays
        natural = _outcome_source(metadata) == "natural-strategy-games"
        values = {
            "outcomes": episode["episode_final_outcomes"],
            "margins": episode["episode_terminal_tower_margins"],
            "seats": episode["episode_learner_players"],
            "styles": np.asarray(metadata["opponents"])[
                episode["episode_opponent_indices"]
            ],
            "decks": np.asarray(metadata["opponent_decks"])[
                episode["episode_opponent_deck_indices"]
            ]
            if natural
            else np.full(corpus.episode_count, "<controlled>"),
            "natural": np.full(corpus.episode_count, natural),
        }
        for name, value in values.items():
            columns[name].append(np.repeat(value, lengths))
    columns = {k: np.concatenate(v)[rows] for k, v in columns.items()}
    selected_features = features[rows]
    prediction = head(selected_features.to(device))
    public = selected_features[:, -18:].cpu().numpy()
    phases = np.asarray(["early", "middle", "late"])[
        np.minimum((public[:, 0] * 3).astype(int), 2)
    ]
    clusters = phase_balanced_matchup_clusters(loaded)
    groups = [
        (
            "development",
            columns["natural"],
            protocol["development_selection"]["opponents"],
            True,
        )
    ]
    if stage == "holdout":
        reserved = (
            columns["decks"] == protocol["final_holdout"]["reserved_original"]["deck"]
        )
        groups = [
            (
                "generated",
                columns["natural"] & ~reserved,
                protocol["generalization_evaluation"]["required_generated_styles"],
                True,
            ),
            (
                "reserved_original",
                columns["natural"] & reserved,
                protocol["final_holdout"]["reserved_original"]["opponents"],
                False,
            ),
        ]
    results = {}
    for name, mask, expected, joint in groups:
        results[name] = evaluate_slices(
            probabilities=prediction.outcome_logits.softmax(-1).cpu().numpy()[mask],
            predicted_margin=prediction.terminal_tower_margin.cpu().numpy()[mask],
            target_margin=columns["margins"][mask],
            outcomes=columns["outcomes"][mask],
            current_margin=((public[:, 8:11].sum(1) - public[:, 11:14].sum(1)) / 3)[
                mask
            ],
            phases=phases[mask],
            seats=columns["seats"][mask],
            styles=columns["styles"][mask],
            clusters=clusters[mask],
            expected_styles=expected,
            prior=prior.cpu().numpy(),
            gates=protocol["gates"],
            design=protocol["generalization_evaluation"],
            seed=seed,
            include_joint=joint,
        )
    full_phase = None
    if protocol["generalization_evaluation"].get("full_phase_margin_gate"):
        full_phase = evaluate_loaded_full_phase_margins(
            head, features, loaded, protocol, stage=stage, device=device, seed=seed,
        )
    return {
        "schema": "clasher.hog26.public-slice-acceptance.v1",
        "passed": all(r["passed"] for r in results.values())
        and (full_phase is None or full_phase["passed"]),
        "groups": results,
        "full_phase_margins": full_phase,
    }


@torch.no_grad()
def evaluate_loaded_full_phase_margins(
    head, features, loaded, protocol, *, stage, device, seed,
):
    """Evaluate every recorded natural state, equally weighting games per phase."""
    from scripts.train_hog26_actor_outcome import _outcome_source

    design = protocol["generalization_evaluation"]
    if design["full_phase_margin_gate"]["weighting"] != "equal-game-within-phase-v1":
        raise ValueError("unknown full-phase margin weighting")
    records = {name: [] for name in ("early", "middle", "late")}
    classification_rows = {name: [] for name in records}
    offset = 0
    for metadata, corpus in loaded:
        selected = _outcome_source(metadata) == "natural-strategy-games"
        if stage == "holdout":
            selected = selected and metadata["seed"] == protocol["final_holdout"]["generated"]["seed"]
        if selected:
            predictions = [
                head(batch.to(device))
                for batch in features[offset:offset + corpus.row_count].split(2048)
            ]
            predicted = torch.cat([p.terminal_tower_margin.cpu() for p in predictions]).numpy()
            probabilities = torch.cat([p.outcome_logits.softmax(-1).cpu() for p in predictions]).numpy()
            public = np.asarray(corpus.arrays["global_features"])
            current = (public[:, 8:11].sum(1) - public[:, 11:14].sum(1)) / 3
            target = np.repeat(corpus.episode_arrays["episode_terminal_tower_margins"],
                               np.diff(corpus.episode_offsets))
            if not all(np.isfinite(a).all() for a in (predicted, current, target)):
                raise ValueError("nonfinite full-phase margin prediction or label")
            for episode, (begin, end) in enumerate(zip(
                corpus.episode_offsets[:-1], corpus.episode_offsets[1:], strict=True
            )):
                cluster = episode_matchup_cluster(metadata, corpus, episode)
                phase_ids = np.minimum((public[begin:end, 0] * 3).astype(int), 2)
                for phase, name in enumerate(records):
                    rows = np.flatnonzero(phase_ids == phase) + begin
                    if not len(rows):
                        continue
                    mae = float(np.abs(predicted[rows] - target[rows]).mean())
                    baseline = float(np.abs(current[rows] - target[rows]).mean())
                    records[name].append({
                        "cluster": cluster, "rows": len(rows), "mae": mae,
                        "baseline_mae": baseline, "improvement": baseline - mae,
                        "outcome": int(corpus.episode_arrays["episode_final_outcomes"][episode]),
                    })
                    classification_rows[name].append((
                        probabilities[rows],
                        np.full(len(rows), corpus.episode_arrays["episode_final_outcomes"][episode]),
                        np.full(len(rows), 1 / len(rows)),
                    ))
        offset += corpus.row_count
    if offset != len(features):
        raise ValueError("full-phase features are misaligned with corpora")
    results = {}
    thresholds = design["phase_margin_learning_gate"]
    for index, (name, rows) in enumerate(records.items()):
        clusters = [r["cluster"] for r in rows]
        interval = clustered_mean_interval(
            [r["improvement"] for r in rows], clusters,
            replicates=protocol["gates"]["cluster_bootstrap_replicates"], seed=seed + index,
        )
        counts = {str(label): len({r["cluster"] for r in rows if r["outcome"] == label})
                  for label in (-1, 0, 1)}
        coverage = len(set(clusters)) >= design["minimum_independent_matchup_clusters_per_slice"] and all(
            counts[str(label)] >= design["minimum_clusters_with_each_decisive_outcome_per_slice"]
            for label in (-1, 1)
        )
        passed = coverage and interval is not None and (
            interval["point"] >= thresholds["minimum_mae_improvement"]
            and interval["lower_95"] >= thresholds["minimum_cluster_bootstrap_lower_95_improvement"]
        )
        classification = None
        classification_passed = False
        if rows:
            inputs = classification_rows[name]
            classification = weighted_outcome_metrics(*[
                np.concatenate([row[i] for row in inputs]) for i in range(3)
            ])
            classification_passed = (
                classification["ece_10"] <= protocol["gates"]["maximum_ece"]
                and max(classification["classwise_ece_10"].values()) <= protocol["gates"]["maximum_ece"]
                and classification["decisive_auc"] is not None
                and classification["decisive_auc"] >= protocol["gates"]["minimum_natural_phase_auc"]
                and classification["mean_probability"]["draw"] <= protocol["gates"]["maximum_natural_draw_probability"]
            )
        if design.get("full_phase_classification_gate"):
            passed = passed and classification_passed
        results[name] = {
            "games": len(rows), "rows": sum(r["rows"] for r in rows),
            "independent_clusters": len(set(clusters)), "clusters_by_outcome": counts,
            "mae": float(np.mean([r["mae"] for r in rows])) if rows else None,
            "baseline_mae": float(np.mean([r["baseline_mae"] for r in rows])) if rows else None,
            "improvement_interval": interval, "coverage_passed": coverage,
            "classification": classification,
            "classification_passed": classification_passed,
            "passed": bool(passed),
        }
    return {"weighting": "equal-game-within-phase-v1",
            "passed": all(r["passed"] for r in results.values()), "phases": results}
