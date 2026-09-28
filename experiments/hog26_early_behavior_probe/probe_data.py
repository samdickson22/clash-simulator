"""One fixed early public representative per training game; style is a target only."""

import hashlib
from dataclasses import dataclass

import numpy as np
from cache_reader import read_complete_cache
from health_features import augment, make_layout
from history_reader import open_history_cache
from scalar_evaluation import EvaluationIndex
from value_contract import CACHE


def array_sha(value):
    value = np.ascontiguousarray(value)
    return hashlib.sha256(memoryview(value).cast('B')).hexdigest()


@dataclass(frozen=True)
class ProbeData:
    matrices: dict[str, np.ndarray]
    labels: np.ndarray
    families: np.ndarray
    folds: np.ndarray
    seats: np.ndarray
    clusters: np.ndarray
    audit: dict


def load_data():
    base, evaluation, complete, _ = read_complete_cache(CACHE)
    history, history_complete = open_history_cache()
    ids, progress = evaluation[0], evaluation[1]
    index = EvaluationIndex(ids, progress)
    rows = np.flatnonzero(index.representative_mask & (index.phases == 0))
    if len(rows) != 6144 or not np.array_equal(ids[rows], np.arange(6144)):
        raise ValueError('exactly one existing early representative per complete game required')
    current = augment(np.array(base[rows], copy=True), make_layout(complete['feature_names']))
    temporal = np.array(history[rows], copy=True)
    base._mmap.close()
    history._mmap.close()
    families, seats, clusters = evaluation[9][rows], evaluation[5][rows], evaluation[8][rows]
    styles = evaluation[6][rows]
    labels = (styles == 'bridge-pressure').astype(np.int64)
    folds = evaluation[7][rows]
    matrices = {'base_public': current, 'entity_history': np.concatenate((current, temporal), axis=1)}
    if matrices['base_public'].shape != (6144, 814) or matrices['entity_history'].shape != (6144, 911):
        raise ValueError('fixed public representation dimensions differ')
    if (labels.sum() != 1024 or len(np.unique(clusters)) != 3072
            or set(styles) != {'balanced', 'random', 'bridge-pressure', 'reactive-defense', 'slow-push', 'spell-control'}):
        raise ValueError('unfiltered training style populations differ')
    for fold in range(4):
        selected = folds != fold
        if selected.sum() != 4608 or labels[selected].sum() != 768:
            raise ValueError('whole-family auxiliary fitting populations differ')
    audit = {'games': 6144, 'clusters': 3072, 'positive_bridge_games': int(labels.sum()),
             'rows_sha256': array_sha(rows), 'label_sha256': array_sha(labels),
             'matrix_sha256': {name: array_sha(value) for name, value in matrices.items()},
             'history_cache_sha256': history_complete['cache']['sha256'],
             'public_prefix_exact': np.array_equal(matrices['entity_history'][:, :814], current),
             'scope': 'Existing early representatives only, with all complete games retained. No outcome target is used. This does not establish full-phase or outcome calibration.'}
    return ProbeData(matrices, labels, families, folds, seats, clusters, audit)
