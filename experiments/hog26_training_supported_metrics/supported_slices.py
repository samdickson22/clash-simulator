"""Diagnostic numerical copy; zero prior allowed only for unobserved outcomes.

The unchanged native evaluator still rejects these priors. This function cannot
establish acceptance, draw support, or natural draw calibration.
"""
from itertools import product
from typing import Any

import numpy as np
import torch

from scripts.hog26_public_slice_gates import clustered_mean_interval


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
    if prior.shape != (3,) or (prior < 0).any() or not np.isfinite(prior).all() or not np.isclose(prior.sum(), 1):
        raise ValueError("invalid training-only prior")
    predicted_margin, target_margin, current_margin, phases, seats, styles, clusters = (
        np.asarray(a) for a in arrays
    )
    if not set(styles).issubset(expected_styles):
        raise ValueError("unexpected opponent in natural acceptance data")
    label_ids = y.astype(int) + 1
    if np.any(prior[label_ids] <= 0):
        raise ValueError("observed label has no training prior support")
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

