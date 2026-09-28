"""Current public health aggregates; no future endpoint or learned auxiliary input."""

from dataclasses import dataclass

import numpy as np

EXTRA_NAMES = ("own.minimum_living_tower_fraction", "enemy.minimum_living_tower_fraction",
               "own.living_tower_count_div3", "enemy.living_tower_count_div3", "public.current_tower_margin")


@dataclass(frozen=True)
class HealthLayout:
    hp: tuple[int, ...]
    confidence: tuple[int, ...]
    globals: tuple[int, ...]


def make_layout(names):
    names = tuple(names)
    if len(names) != 809 or len(set(names)) != 809:
        raise ValueError("expected the frozen809-column public cache")
    hp = tuple(names.index(f"global{i}") for i in range(8, 14))
    confidence = tuple(names.index(f"global{i}.confidence") for i in range(8, 14))
    globals_ = tuple(names.index(f"global{i}") for i in range(18)) + tuple(names.index(f"global{i}.confidence") for i in range(18))
    return HealthLayout(hp, confidence, globals_)


def augment(base, layout):
    base = np.asarray(base)
    if base.dtype != np.float32 or base.ndim != 2 or base.shape[1] != 809 or not np.isfinite(base).all():
        raise ValueError("expected finite float32 public features")
    hp = np.ascontiguousarray(base[:, layout.hp])
    if not np.all(base[:, layout.confidence] == 1) or ((hp < 0) | (hp > 1)).any():
        raise ValueError("public tower fractions must be fully available and normalized")
    extra = np.empty((len(base), 5), dtype=np.float32)
    for side, columns in enumerate((slice(0, 3), slice(3, 6))):
        values = hp[:, columns]
        alive = values > 0
        minimum = np.where(alive, values, np.inf).min(1)
        extra[:, side] = np.where(alive.any(1), minimum, 0)
        extra[:, side + 2] = alive.sum(1) / 3
    extra[:, 4] = (hp[:, :3].sum(1) - hp[:, 3:].sum(1)) / 3
    return np.concatenate((base, extra), axis=1)


def materialize_fitting(cache_path, cache_shape, rows, layout, *, chunk_rows=4096):
    rows = np.asarray(rows)
    if (rows.ndim != 1 or not len(rows) or not np.array_equal(rows, np.unique(rows))
            or rows[0] < 0 or rows[-1] >= cache_shape[0] or cache_shape[1] != 809 or chunk_rows <= 0):
        raise ValueError("distinct ordered fitting rows and the exact cache shape required")
    result = np.empty((len(rows), 814), dtype=np.float64)
    for start in range(0, len(rows), chunk_rows):
        chosen = rows[start:start + chunk_rows]
        mapped = np.memmap(cache_path, mode="r", dtype="<f4", shape=tuple(cache_shape))
        block = np.array(mapped[chosen], dtype=np.float32, copy=True)
        mapped._mmap.close()
        result[start:start + len(chosen)] = augment(block, layout)
    return result
