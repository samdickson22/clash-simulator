"""Continuous public-clock weights and bounded convex expert inference."""

import numpy as np
from health_features import augment


def overlap_weights(progress):
    progress = np.asarray(progress, dtype=np.float64)
    if progress.ndim != 1 or not np.isfinite(progress).all() or (progress < 0).any():
        raise ValueError('finite nonnegative actor-visible clock required')
    weights = np.empty((len(progress), 3), dtype=np.float64)
    weights[:, 0] = np.clip(3 * (.5 - progress), 0, 1)
    weights[:, 2] = np.clip(3 * (progress - .5), 0, 1)
    weights[:, 1] = 1 - weights[:, 0] - weights[:, 2]
    if (weights < 0).any() or not np.allclose(weights.sum(1), 1, rtol=0, atol=1e-15):
        raise ValueError('convex expert weights required')
    return weights


def blended_predict(models, features, clock_column):
    features = np.asarray(features)
    if features.ndim != 2 or features.shape[1] != 814 or len(models) != 3:
        raise ValueError('three overlapping experts and814 public columns required')
    weights = overlap_weights(features[:, clock_column])
    result = np.zeros(len(features), dtype=np.float64)
    for expert, model in enumerate(models):
        selected = weights[:, expert] > 0
        if selected.any():
            block = features[selected]
            prediction = np.clip(block[:, -1] + model.predict(block), -1, 1)
            result[selected] += weights[selected, expert] * prediction
    if not np.isfinite(result).all() or (np.abs(result) > 1 + 1e-12).any():
        raise ValueError('finite bounded convex forecast required')
    return np.clip(result, -1, 1)


def predict_cache(models, path, shape, layout):
    result = np.empty(shape[0], dtype=np.float64)
    for start in range(0, shape[0], 4096):
        end = min(start + 4096, shape[0])
        mapped = np.memmap(path, mode='r', dtype='<f4', shape=shape)
        block = np.array(mapped[start:end], copy=True)
        mapped._mmap.close()
        result[start:end] = blended_predict(models, augment(block, layout), layout.globals[0])
    return result
