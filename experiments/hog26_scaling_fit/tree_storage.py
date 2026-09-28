"""Build only fitting-family tree rows in sklearn's required float64 dtype."""
import numpy as np
from scalar_features import build_game_features, feature_names


def fitting_features(games, fit_indices, vocabulary_size, *, max_bytes=10*1024**3):
    indices = list(fit_indices)
    if not indices or indices != sorted(set(indices)):
        raise ValueError('fitting games must be distinct and in original order')
    if min(indices) < 0 or max(indices) >= len(games):
        raise ValueError('fitting game index out of range')
    rows = sum(len(games[i].public['global_features']) for i in indices)
    columns = len(feature_names(vocabulary_size))
    required = rows*columns*np.dtype(np.float64).itemsize
    if required > max_bytes:
        raise MemoryError(f'fitting tree matrix needs {required} bytes; limit {max_bytes}')
    result = np.empty((rows, columns), dtype=np.float64)
    offset = 0
    for index in indices:
        values = build_game_features(**games[index].public, vocabulary_size=vocabulary_size)
        result[offset:offset+len(values)] = values
        offset += len(values)
    return result


def predict_margin(model, games, vocabulary_size):
    predictions = []
    for game in games:
        values = build_game_features(**game.public, vocabulary_size=vocabulary_size)
        globals_ = game.public['global_features']
        current = (globals_[:,8:11].sum(1)-globals_[:,11:14].sum(1))/3
        predictions.append(np.clip(current+model.predict(values),-1,1))
    return np.concatenate(predictions)
