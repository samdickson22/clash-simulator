"""Fixed public-input estimators for the expanded training comparison."""

import sys

import numpy as np
import torch
from scalar_models import GlobalWDL
from torch.nn import functional as F

TREE_SETTINGS = {'learning_rate': .05, 'max_iter': 100, 'max_leaf_nodes': 15,
                 'min_samples_leaf': 20, 'l2_regularization': 1., 'max_bins': 255,
                 'early_stopping': False, 'max_features': 1.}


def new_trees(seed, *, probe_iterations=None):
    sys.path.insert(0, '/Users/sam/.cache/clasher-margin-tree-diagnostic')
    from sklearn.ensemble import (
        HistGradientBoostingClassifier,
        HistGradientBoostingRegressor,
    )

    settings = {**TREE_SETTINGS, 'random_state': int(seed)}
    if probe_iterations is not None:
        settings['max_iter'] = int(probe_iterations)
    return (HistGradientBoostingClassifier(loss='log_loss', **settings),
            HistGradientBoostingRegressor(loss='absolute_error', **settings))


def canonical_probabilities(model, features):
    classes = np.asarray(model.classes_)
    if classes.ndim != 1 or not np.isin(classes, (0, 1, 2)).all() or len(np.unique(classes)) != len(classes):
        raise ValueError('classifier classes must be distinct canonical L/D/W integers')
    raw = model.predict_proba(features)
    result = np.zeros((len(features), 3), dtype=np.float64)
    result[:, classes.astype(int)] = raw
    if not np.isfinite(result).all() or (result < 0).any() or not np.allclose(result.sum(1), 1):
        raise ValueError('invalid class probabilities')
    return result


def fit_cached_globals(features, labels, weights, *, seed, epochs=30, batch_rows=512, log=None):
    if features.dtype != np.float32 or features.shape != (len(labels), 36):
        raise ValueError('expected cached masked globals and confidences')
    if not np.isclose(weights.sum(), 1) or (weights < 0).any():
        raise ValueError('fitting WDL weights must sum to one')
    torch.manual_seed(seed)
    model = GlobalWDL()
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    x = torch.from_numpy(features)
    targets = torch.from_numpy(np.asarray(labels, dtype=np.int64))
    w = torch.from_numpy(weights).float()
    count = len(features)
    for epoch in range(epochs):
        order = torch.randperm(count)
        for start in range(0, count, batch_rows):
            indices = order[start:start + batch_rows]
            optimizer.zero_grad(set_to_none=True)
            loss = (F.cross_entropy(model.network(x[indices]), targets[indices], reduction='none') * w[indices]).sum() * count / len(indices)
            if not torch.isfinite(loss):
                raise FloatingPointError('nonfinite globals loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
        if log:
            log({'epoch': epoch + 1})
    return model.eval()
