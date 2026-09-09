"""Public-history constant-damage-rate diagnostic for overtime termination."""

import numpy as np


def overtime_damage_race(public, episode_offsets, *, window=20):
    """Project recent damage until the first surviving tower falls or time expires."""
    if window < 1 or public.ndim != 2 or public.shape[1] != 18:
        raise ValueError("damage race needs public globals and a positive history window")
    delta = np.zeros(len(public), dtype=np.float32)
    horizon = np.zeros(len(public), dtype=np.float32)
    for episode in range(len(episode_offsets) - 1):
        begin, end = episode_offsets[episode:episode + 2]
        rows = np.arange(begin, end)
        past = np.maximum(begin, rows - window)
        hp = public[rows, 8:14]
        elapsed = public[rows, 0] - public[past, 0]
        damage = np.maximum(public[past, 8:14] - hp, 0)
        rates = np.divide(damage, elapsed[:, None], out=np.zeros_like(damage),
                          where=elapsed[:, None] > 0)
        times = np.divide(hp, rates, out=np.full_like(hp, np.inf),
                          where=(hp > 0) & (rates > 0))
        remaining = np.maximum(public[rows, 1], 0)
        duration = np.minimum(times.min(1), remaining)
        duration = np.where(public[rows, 4] > 0, duration, 0)
        losses = np.minimum(rates * duration[:, None], hp)
        delta[rows] = (losses[:, 3:].sum(1) - losses[:, :3].sum(1)) / 3
        horizon[rows] = duration
    return delta, horizon
