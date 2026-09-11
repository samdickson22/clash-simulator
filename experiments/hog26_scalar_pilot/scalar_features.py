"""Predeclared scalar-public-summary-v1 tree features, one complete game per call.

Order: own then enemy; within each, troop/building/projectile/nonprojectile-effect.
Each group contains count, then mean/max pairs in SELECTED_INDICES order, then
16 occupancy counts in y-major/x-minor order. Next: 18 confidence-masked globals,
18 global confidences, four ordered vocabulary-sized confidence-weighted one-hot
hands, three blocks of 18 global differences (lags 1,5,20), then their three flags.

Available feature reductions average confidence-multiplied values over entries
with positive confidence; unavailable entries never enter means or maxima.
Occupancy uses raw normalized visible xy with positive coordinate confidence.
Lag differences require both endpoints available for that coordinate, and compare
confidence-masked globals. Lag flags describe same-game past-row existence only.
No fitted preprocessing, entity identity ordinal, metadata, labels, or future
fields are accepted. Separate calls are mandatory at game boundaries. Geometry
is intentionally absent: the frozen plan specifies it only for the neural model.
"""

import numpy as np

SELECTED_INDICES = (0, 1, 9, 10, 12, 23, 24, 25, 26, 30)
LAGS = (1, 5, 20)
SIDES = (("own", 2), ("enemy", 3))
KINDS = (("troop", 4), ("building", 5), ("projectile", 6), ("effect", 7))


def feature_names(vocabulary_size):
    if isinstance(vocabulary_size, bool) or not isinstance(vocabulary_size, int) or vocabulary_size < 3:
        raise ValueError("vocabulary_size must be a fixed integer >= 3")
    names = []
    for side, _ in SIDES:
        for kind, _ in KINDS:
            prefix = f"{side}.{kind}"
            names.append(f"{prefix}.count")
            for index in SELECTED_INDICES:
                names.extend((f"{prefix}.feature{index}.mean", f"{prefix}.feature{index}.max"))
            names.extend(f"{prefix}.cell{y}_{x}.count" for y in range(4) for x in range(4))
    names.extend(f"global{j}" for j in range(18))
    names.extend(f"global{j}.confidence" for j in range(18))
    names.extend(f"hand{slot}.token{token}" for slot in range(4) for token in range(vocabulary_size))
    names.extend(f"lag{lag}.global{j}.difference" for lag in LAGS for j in range(18))
    names.extend(f"lag{lag}.available" for lag in LAGS)
    return tuple(names)


def _confidence(value, shape, name, mask=None):
    value = np.asarray(value, dtype=np.float32)
    if value.shape != shape:
        raise ValueError(f"wrong {name} shape")
    if mask is not None:
        value = np.where(mask, value, 0)
    if not np.isfinite(value).all() or ((value < 0) | (value > 1)).any():
        raise ValueError(f"invalid {name}")
    return value


def _available(value, confidence, name):
    value = np.asarray(value, dtype=np.float32)
    if value.shape != confidence.shape:
        raise ValueError(f"wrong {name} shape")
    result = np.zeros_like(value)
    np.multiply(value, confidence, out=result, where=confidence > 0)
    if not np.isfinite(result).all():
        raise ValueError(f"nonfinite available {name}")
    return result


def build_game_features(*, entity_ids, entity_features, entity_mask,
                        entity_id_confidence, entity_feature_confidence,
                        hand_ids, hand_id_confidence, global_features,
                        global_feature_confidence, vocabulary_size):
    """Return float32 [decisions, features]; this invocation is exactly one game."""
    names = feature_names(vocabulary_size)
    ids = np.asarray(entity_ids)
    if ids.ndim != 2:
        raise ValueError("expected per-game [decisions, entities] arrays")
    t, n = ids.shape
    if t < 1:
        raise ValueError("empty game")
    mask = np.asarray(entity_mask)
    if mask.shape != (t, n) or not np.isin(mask, (0, 1)).all():
        raise ValueError("invalid entity_mask")
    mask = mask.astype(bool)
    _confidence(entity_id_confidence, (t, n), "entity_id_confidence", mask)
    fc = _confidence(entity_feature_confidence, (t, n, 32), "entity_feature_confidence", mask[..., None])
    f = _available(entity_features, fc, "entity_features")
    raw = np.asarray(entity_features)
    gc = _confidence(global_feature_confidence, (t, 18), "global_feature_confidence")
    g = _available(global_features, gc, "global_features")
    hc = _confidence(hand_id_confidence, (t, 4), "hand_id_confidence")
    hand = np.asarray(hand_ids)
    if hand.shape != (t, 4):
        raise ValueError("wrong hand_ids shape")
    known_hand = hc > 0
    observed = hand[known_hand]
    if not np.isfinite(observed).all() or ((observed < 0) | (observed >= vocabulary_size) | (observed != np.floor(observed))).any():
        raise ValueError("available hand token outside fixed vocabulary")
    blocks = []
    for _, side in SIDES:
        for _, kind in KINDS:
            selected = mask & (fc[..., side] > 0) & (fc[..., kind] > 0) & (raw[..., side] > .5) & (raw[..., kind] > .5)
            blocks.append(selected.sum(1, keepdims=True))
            for index in SELECTED_INDICES:
                available = selected & (fc[..., index] > 0)
                count = available.sum(1)
                total = np.where(available, f[..., index], 0).sum(1, dtype=np.float64)
                mean = total / np.maximum(count, 1)
                maximum = np.max(np.where(available, f[..., index], -np.inf), axis=1, initial=-np.inf)
                maximum = np.where(count > 0, maximum, 0)
                blocks.extend((mean[:, None], maximum[:, None]))
            xy_available = selected & (fc[..., 0] > 0) & (fc[..., 1] > 0)
            xy = np.where(xy_available[..., None], raw[..., :2], 0)
            if (((xy < 0) | (xy > 1)) & xy_available[..., None]).any():
                raise ValueError("available position outside normalized arena")
            cells = np.minimum((xy * 4).astype(np.int64), 3)
            occupancy = np.stack([(xy_available & (cells[..., 0] == x) & (cells[..., 1] == y)).sum(1)
                                  for y in range(4) for x in range(4)], axis=1)
            blocks.append(occupancy)
    blocks.extend((g, gc))
    onehot = np.zeros((t, 4, vocabulary_size), dtype=np.float32)
    rows, slots = np.nonzero(known_hand)
    onehot[rows, slots, hand[known_hand].astype(np.int64)] = hc[known_hand]
    blocks.append(onehot.reshape(t, 4 * vocabulary_size))
    flags = np.zeros((t, len(LAGS)), dtype=np.float32)
    for column, lag in enumerate(LAGS):
        differences = np.zeros((t, 18), dtype=np.float32)
        if t > lag:
            both_available = (gc[lag:] > 0) & (gc[:-lag] > 0)
            differences[lag:] = np.where(both_available, g[lag:] - g[:-lag], 0)
            flags[lag:, column] = 1
        blocks.append(differences)
    blocks.append(flags)
    result = np.concatenate(blocks, axis=1).astype(np.float32)
    if result.shape != (t, len(names)) or not np.isfinite(result).all():
        raise ValueError("invalid summary feature result")
    return result
