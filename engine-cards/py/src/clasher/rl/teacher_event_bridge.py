"""Behavior-preserving bridge from the retained Hog hazard policy.

This adapter is intentionally narrow: it converts the frozen control's
calibrated placement hazard and conditional card/tile logits into the new
continuous-time distribution.  It does not load a checkpoint, inspect private
state, or support champion abilities.  The latter remains a separate competing
event in the fresh architecture.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import Tensor

from .event_policy import (
    ABILITY_ACTION,
    ContinuousTimeActionDistribution,
    continuous_time_action_distribution,
    raw_rate_from_interval_probability,
)


@dataclass(frozen=True)
class LegacyHazardTeacherFactors:
    """Calibrated retained-policy timing plus its exact action distribution."""

    interval_play_probability: Tensor
    distribution: ContinuousTimeActionDistribution


def legacy_hazard_teacher_factors(
    hazard_logits: Tensor,
    card_logits: Tensor,
    location_logits: Tensor,
    action_mask: Tensor,
    delta_seconds: Tensor,
    *,
    positive_weight: float,
) -> LegacyHazardTeacherFactors:
    """Convert retained weighted-BCE hazard outputs without changing behavior."""

    if not math.isfinite(positive_weight) or positive_weight < 1.0:
        raise ValueError("retained hazard positive weight must be finite and >= 1")
    if hazard_logits.shape != delta_seconds.shape:
        raise ValueError("retained hazard logits and elapsed seconds differ")
    if bool(action_mask[..., ABILITY_ACTION].any()):
        raise ValueError("the Hog teacher bridge does not support champion abilities")
    interval_probability = torch.sigmoid(
        hazard_logits - math.log(positive_weight)
    )
    raw_play_rate = raw_rate_from_interval_probability(
        interval_probability, delta_seconds
    )
    raw_ability_rate = torch.full_like(raw_play_rate, -torch.inf)
    distribution = continuous_time_action_distribution(
        raw_play_rate,
        raw_ability_rate,
        card_logits,
        location_logits,
        action_mask,
        delta_seconds,
    )
    return LegacyHazardTeacherFactors(
        interval_play_probability=interval_probability,
        distribution=distribution,
    )


__all__ = ["LegacyHazardTeacherFactors", "legacy_hazard_teacher_factors"]
