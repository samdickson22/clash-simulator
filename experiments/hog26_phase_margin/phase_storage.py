"""Route only by the existing public clock, with bounded cache reads."""

import numpy as np
from health_features import augment
from scalar_evaluation import phase_ids


def routed_predict(models, features, clock_column):
    features = np.asarray(features)
    if features.ndim != 2 or features.shape[1] != 814 or len(models) != 3:
        raise ValueError('three phase regressors and814 public columns required')
    phases = phase_ids(features[:, clock_column])
    result = np.empty(len(features), dtype=np.float64)
    for phase, model in enumerate(models):
        selected = phases == phase
        if selected.any():
            result[selected] = np.clip(features[selected, -1] + model.predict(features[selected]), -1, 1)
    if not np.isfinite(result).all():
        raise ValueError('nonfinite phase margin')
    return result


def predict_cache(models, path, shape, layout):
    result = np.empty(shape[0], dtype=np.float64)
    for start in range(0, shape[0], 4096):
        end = min(start + 4096, shape[0])
        mapped = np.memmap(path, mode='r', dtype='<f4', shape=shape)
        block = np.array(mapped[start:end], copy=True)
        mapped._mmap.close()
        result[start:end] = routed_predict(models, augment(block, layout), layout.globals[0])
    return result


def normalized_phase_weights(original, rows):
    selected = np.asarray(original[rows], dtype=np.float64)
    if not len(selected) or not np.isfinite(selected).all() or (selected <= 0).any():
        raise ValueError('positive existing fitting margin weights required')
    return selected * (len(selected) / selected.sum())
