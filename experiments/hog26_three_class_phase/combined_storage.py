"""Bounded public feature reads across separately stored natural/control caches."""

import numpy as np
from controls_cache_contract import OUTPUT as CONTROLS
from health_features import augment
from scalar_evaluation import phase_ids
from value_contract import CACHE
from value_models import canonical_probabilities


def read_rows(data, rows):
    rows = np.asarray(rows, dtype=np.int64)
    if rows.ndim != 1 or (len(rows) and (rows.min() < 0 or rows.max() >= data['rows'])):
        raise ValueError('valid combined public row indices required')
    result = np.empty((len(rows), 814), dtype=np.float32)
    natural = rows < data['natural_rows']
    if natural.any():
        mapped = np.memmap(CACHE / 'features.f32', mode='r', dtype='<f4', shape=tuple(data['natural_shape']))
        block = np.array(mapped[rows[natural]], copy=True)
        mapped._mmap.close()
        result[natural] = augment(block, data['health'])
    if (~natural).any():
        mapped = np.memmap(CONTROLS / 'features.f32', mode='r', dtype='<f4', shape=tuple(data['control']['shape']))
        block = np.array(mapped[rows[~natural] - data['natural_rows']], copy=True)
        mapped._mmap.close()
        result[~natural] = block
    return result


def materialize(data, rows):
    rows = np.asarray(rows, dtype=np.int64)
    if not len(rows) or not np.array_equal(rows, np.unique(rows)):
        raise ValueError('nonempty distinct ordered fitting rows required')
    result = np.empty((len(rows), 814), dtype=np.float64, order='F')
    for start in range(0, len(rows), 4096):
        result[start:start + 4096] = read_rows(data, rows[start:start + 4096])
    return result


def routed_probabilities(models, features, clock_column):
    if len(models) != 3 or features.ndim != 2 or features.shape[1] != 814:
        raise ValueError('three classifiers and814public features required')
    phase = phase_ids(features[:, clock_column])
    result = np.empty((len(features), 3), dtype=np.float64)
    for index, model in enumerate(models):
        selected = phase == index
        if selected.any():
            result[selected] = canonical_probabilities(model, features[selected])
    return result


def predict(data, models):
    probability = np.empty((data['rows'], 3), dtype=np.float64)
    for start in range(0, data['rows'], 4096):
        end = min(start + 4096, data['rows'])
        features = read_rows(data, np.arange(start, end))
        probability[start:end] = routed_probabilities(models, features, data['health'].globals[0])
    return probability
