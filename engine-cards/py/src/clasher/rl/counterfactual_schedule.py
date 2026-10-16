from __future__ import annotations

from itertools import pairwise


def phase_balanced_query_ticks(
    *,
    minimum_tick: int,
    max_ticks: int,
    states_per_game: int,
    decision_interval: int,
    phase_boundaries: tuple[int, ...] = (),
) -> tuple[int, ...]:
    """Spread targets while preserving exact, externally supplied phase starts."""

    if minimum_tick < 0 or max_ticks <= minimum_tick:
        raise ValueError("counterfactual tick range is invalid")
    if states_per_game <= 0 or decision_interval <= 0:
        raise ValueError("counterfactual schedule sizes must be positive")
    last_tick = max_ticks - decision_interval
    if last_tick < minimum_tick:
        raise ValueError("counterfactual tick range has no decision boundary")
    span = last_tick - minimum_tick
    targets = [
        ((minimum_tick + (index * span) // states_per_game) // decision_interval)
        * decision_interval
        for index in range(states_per_game)
    ]
    for boundary in phase_boundaries:
        if (
            boundary <= minimum_tick
            or boundary > last_tick
            or boundary % decision_interval
        ):
            raise ValueError("counterfactual phase boundary is invalid")
        replacement = next(
            (index for index, target in enumerate(targets) if target >= boundary),
            None,
        )
        if replacement is None:
            raise ValueError("counterfactual phase boundary has no target slot")
        targets[replacement] = boundary
    targets_tuple = tuple(targets)
    if len(set(targets_tuple)) != len(targets_tuple):
        raise ValueError("counterfactual schedule has duplicate tick targets")
    if any(right <= left for left, right in pairwise(targets_tuple)):
        raise ValueError("counterfactual phase boundaries break target ordering")
    return targets_tuple


def should_query_phase_balanced_counterfactual(
    *,
    decision_index: int,
    last_query_decision: int | None,
    tick: int,
    collected: int,
    target_ticks: tuple[int, ...],
    minimum_decision_spacing: int,
    can_play: bool,
) -> bool:
    """Select the next due public decision without front-loading one game."""

    if minimum_decision_spacing <= 0:
        raise ValueError("minimum decision spacing must be positive")
    if collected < 0 or collected > len(target_ticks):
        raise ValueError("collected counterfactual count is invalid")
    if collected == len(target_ticks):
        return False
    return bool(
        tick >= target_ticks[collected]
        and can_play
        and (
            last_query_decision is None
            or decision_index - last_query_decision >= minimum_decision_spacing
        )
    )
