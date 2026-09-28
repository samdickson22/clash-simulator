"""Causal history of already masked public summaries, with explicit reset checks."""

from collections import deque
from dataclasses import dataclass

import numpy as np

LAGS = (1, 5, 20)
WINDOW = 20


def observable_names():
    result = []
    for side in ('own', 'enemy'):
        result.extend(f'{side}.{kind}.count' for kind in ('troop', 'building', 'projectile', 'effect'))
        result.extend(f'{side}.troop.feature{index}.mean' for index in (0, 1))
        for name in ('visible_hp_proxy', 'base_direct_dps', 'enemy_crown_dps_proximity'):
            result.extend(f'physical.{side}.troop.{name}.{reduction}' for reduction in ('sum_div128', 'confidence_div128'))
    return tuple(result)


def history_names():
    names = tuple(f'public_history.lag{lag}.{name}.difference' for lag in LAGS for name in observable_names())
    names += tuple(f'public_history.window20.{name}.mean_absolute_change' for name in observable_names())
    return (*names, 'public_history.window20.transition_fraction')


@dataclass(frozen=True)
class HistoryLayout:
    columns: tuple[int, ...]
    clock: int
    clock_confidence: int
    lag_flags: tuple[int, ...]


def make_layout(names):
    names = tuple(names)
    if len(names) != 809 or len(set(names)) != 809:
        raise ValueError('the frozen 809 public feature names are required')
    columns = tuple(names.index(name) for name in observable_names())
    return HistoryLayout(columns, names.index('global0'), names.index('global0.confidence'),
                         tuple(names.index(f'lag{lag}.available') for lag in LAGS))


def build_game_history(base, layout):
    """Exactly one complete public prefix; its future length affects no earlier row."""
    base = np.asarray(base)
    if base.ndim != 2 or base.shape[1] != 809 or base.dtype != np.float32 or not len(base) or not np.isfinite(base).all():
        raise ValueError('nonempty finite float32 public prefixes with 809 columns required')
    time = base[:, layout.clock]
    if not np.all(base[:, layout.clock_confidence] == 1) or (np.diff(time) < 0).any():
        raise ValueError('public clock must be available and ordered within one game')
    count = np.arange(len(base))
    if not np.array_equal(base[:, layout.lag_flags], count[:, None] >= np.array(LAGS)):
        raise ValueError('global lag flags do not match a reset public game prefix')
    values = np.ascontiguousarray(base[:, layout.columns])
    width = len(layout.columns)
    result = np.zeros((len(base), len(history_names())), dtype=np.float32)
    for slot, lag in enumerate(LAGS):
        if len(base) > lag:
            result[lag:, slot * width:(slot + 1) * width] = values[lag:] - values[:-lag]
    delta = np.zeros_like(values)
    delta[1:] = np.abs(values[1:] - values[:-1])
    total = np.zeros(values.shape, dtype=np.float64)
    # Fixed newest-to-oldest addition order matches the online state exactly.
    for lag in range(WINDOW):
        if lag < len(values):
            total[lag:] += delta[:len(values) - lag]
    transitions = np.minimum(count, WINDOW)
    result[:, len(LAGS) * width:-1] = total / np.maximum(transitions, 1)[:, None]
    result[:, -1] = transitions / WINDOW
    if result.shape[1] != 97 or not np.isfinite(result).all():
        raise ValueError('invalid public history features')
    return result


class HistoryState:
    """One actor's public observation prefix; clone this state for a causal branch."""

    def __init__(self, layout):
        self.layout = layout
        self.frames = deque(maxlen=WINDOW + 1)
        self.seen = 0
        self.last_clock = None

    def step(self, base_row):
        row = np.asarray(base_row)
        if row.shape != (809,) or row.dtype != np.float32 or not np.isfinite(row).all():
            raise ValueError('one finite float32 public row is required')
        clock = float(row[self.layout.clock])
        if (row[self.layout.clock_confidence] != 1 or (self.last_clock is not None and clock < self.last_clock)
                or not np.array_equal(row[list(self.layout.lag_flags)], np.array([self.seen >= lag for lag in LAGS]))):
            raise ValueError('history state is unprimed or crossed a game boundary')
        values = row[list(self.layout.columns)].copy()
        frames = deque(self.frames, maxlen=WINDOW + 1)
        frames.append(values)
        width = len(values)
        output = np.zeros(len(history_names()), dtype=np.float32)
        for slot, lag in enumerate(LAGS):
            if self.seen >= lag:
                output[slot * width:(slot + 1) * width] = values - frames[-lag - 1]
        total = np.zeros(width, dtype=np.float64)
        if len(frames) > 1:
            changes = np.abs(np.diff(np.stack(frames), axis=0))
            for change in changes[::-1]:
                total += change
        output[len(LAGS) * width:-1] = total / max(min(self.seen, WINDOW), 1)
        output[-1] = min(self.seen, WINDOW) / WINDOW
        if not np.isfinite(output).all():
            raise ValueError('public history arithmetic became nonfinite')
        self.frames = frames
        self.seen += 1
        self.last_clock = clock
        return output
