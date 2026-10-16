"""Allocation-lean exact helpers for oracle candidate sampling."""

from __future__ import annotations

import numpy as np


def sample_action_subset(
    legal_actions: np.ndarray,
    *,
    sample_limit: int,
    no_op_action: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Match the oracle's sorted subset and RNG trace without Python sets/lists."""
    if legal_actions.size <= sample_limit:
        return legal_actions

    no_op = int(no_op_action)
    other = legal_actions[legal_actions != no_op]
    needed = max(0, sample_limit - 1)
    if needed <= 0 or other.size == 0:
        return np.asarray([no_op], dtype=np.int64)

    picks = rng.choice(
        other,
        size=min(needed, other.size),
        replace=False,
    )
    selected = np.empty((picks.size + 1,), dtype=np.int64)
    selected[0] = no_op
    selected[1:] = picks
    selected.sort()
    return selected
