"""Experimental causal history inputs for training-family margin diagnostics."""

from itertools import pairwise

import numpy as np

from clasher.rl.public_margin_dynamics import overtime_damage_race


def public_history_features(public, episode_offsets, *, windows=(1, 5, 20)):
    """Keep public changes over past decisions and the current globals suffix."""
    public = np.asarray(public, dtype=np.float32)
    offsets = np.asarray(episode_offsets)
    if public.ndim != 2 or public.shape[1] != 18 or not np.isfinite(public).all():
        raise ValueError("history requires finite public globals with width 18")
    if (offsets.ndim != 1 or len(offsets) < 2 or offsets[0] != 0
            or offsets[-1] != len(public) or np.any(np.diff(offsets) <= 0)
            or not np.issubdtype(offsets.dtype, np.integer)):
        raise ValueError("history requires complete nonempty episode boundaries")
    if not windows or any(type(w) is not int or w < 1 for w in windows):
        raise ValueError("history windows must be positive integer decision counts")
    changes = []
    for window in windows:
        delta = np.zeros_like(public)
        for begin, end in pairwise(offsets):
            rows = np.arange(begin, end)
            delta[rows] = public[rows] - public[np.maximum(begin, rows - window)]
        changes.append(delta)
    race, horizon = overtime_damage_race(public, offsets, window=max(windows))
    return np.concatenate([*changes, race[:, None], horizon[:, None], public], axis=1)
