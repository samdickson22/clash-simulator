from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PrototypeDecision:
    candidate: str
    score: float
    runner_up_score: float
    margin: float
    accepted: bool


def prototype_decisions(
    queries: np.ndarray,
    prototypes: np.ndarray,
    labels: list[str],
    *,
    minimum_score: float,
    minimum_margin: float,
) -> list[PrototypeDecision]:
    if queries.ndim != 2 or prototypes.ndim != 2:
        raise ValueError("queries and prototypes must be matrices")
    if queries.shape[1] != prototypes.shape[1]:
        raise ValueError("query and prototype dimensions differ")
    if prototypes.shape[0] != len(labels) or not labels:
        raise ValueError("labels must match a nonempty prototype matrix")
    if not 0.0 <= minimum_score <= 1.0 or not 0.0 <= minimum_margin <= 1.0:
        raise ValueError("prototype thresholds must be in [0, 1]")

    scores = queries @ prototypes.T
    unique_labels = sorted(set(labels))
    label_indices = {
        label: np.asarray([index for index, value in enumerate(labels) if value == label])
        for label in unique_labels
    }
    output: list[PrototypeDecision] = []
    for row in scores:
        class_scores = {
            label: float(row[indices].max()) for label, indices in label_indices.items()
        }
        ordered = sorted(class_scores, key=lambda label: class_scores[label], reverse=True)
        candidate = ordered[0]
        score = class_scores[candidate]
        runner = class_scores[ordered[1]] if len(ordered) > 1 else -1.0
        margin = score - runner
        output.append(
            PrototypeDecision(
                candidate=candidate,
                score=score,
                runner_up_score=runner,
                margin=margin,
                accepted=score >= minimum_score and margin >= minimum_margin,
            )
        )
    return output


def complete_unique_deck(decisions: list[PrototypeDecision]) -> bool:
    return bool(
        len(decisions) == 8
        and all(row.accepted for row in decisions)
        and len({row.candidate for row in decisions}) == 8
    )
