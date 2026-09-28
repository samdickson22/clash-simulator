"""Bounded resident reads of the complete public feature cache."""

import itertools

import numpy as np
import torch
from health_features import augment
from value_models import canonical_probabilities


def global_matrix(path, shape, layout):
    result = np.empty((shape[0], 36), dtype=np.float32)
    for start in range(0, shape[0], 8192):
        mapped = np.memmap(path, mode='r', dtype='<f4', shape=shape)
        result[start:start + 8192] = mapped[start:start + 8192, layout.globals]
        mapped._mmap.close()
    return result


def predict_globals(model, features, offsets):
    result = np.empty((len(features), 3), dtype=np.float32)
    with torch.inference_mode():
        for start, end in itertools.pairwise(offsets):
            result[start:end] = model.network(torch.from_numpy(features[start:end])).softmax(-1).numpy()
    return result


def predict_trees(classifier, regressor, path, shape, layout):
    probability = np.empty((shape[0], 3), dtype=np.float64)
    margin = np.empty(shape[0], dtype=np.float64)
    for start in range(0, shape[0], 4096):
        end = min(start + 4096, shape[0])
        mapped = np.memmap(path, mode='r', dtype='<f4', shape=shape)
        block = np.array(mapped[start:end], copy=True)
        mapped._mmap.close()
        features = augment(block, layout)
        probability[start:end] = canonical_probabilities(classifier, features)
        margin[start:end] = np.clip(features[:, -1] + regressor.predict(features), -1, 1)
    return probability, margin


def materialize_fitting(path, shape, rows, layout, *, chunk_rows=4096):
    """Column-contiguous float64 fitting matrix; identical public values."""
    rows = np.asarray(rows)
    if (rows.ndim != 1 or not len(rows) or not np.array_equal(rows, np.unique(rows))
            or rows[0] < 0 or rows[-1] >= shape[0] or shape[1] != 809 or chunk_rows <= 0):
        raise ValueError('distinct ordered fitting rows and exact cache shape required')
    result = np.empty((len(rows), 814), dtype=np.float64, order='F')
    for start in range(0, len(rows), chunk_rows):
        chosen = rows[start:start + chunk_rows]
        mapped = np.memmap(path, mode='r', dtype='<f4', shape=tuple(shape))
        block = np.array(mapped[chosen], dtype=np.float32, copy=True)
        mapped._mmap.close()
        result[start:start + len(chosen)] = augment(block, layout)
    return result
