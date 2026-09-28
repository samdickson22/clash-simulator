"""Causal physical summaries using only identities and fields visible to the actor."""

import numpy as np
from body_stats import STAT_NAMES, STATIC_INDICES
from residual_features import numeric_features
from scalar_features import _available, _confidence

BODY_NAMES = (*STAT_NAMES, "visible_hp_proxy", "visible_shield_proxy", "flying_hp_proxy",
              "anti_air_dps_proxy", "building_dps_proxy", "enemy_crown_dps_proximity",
              "enemy_crown_hp_proximity", "own_crown_anti_air_proximity")
GROUPS = tuple((side, index, kind) for side, index in (("own", 2), ("enemy", 3))
               for kind in ("troop", "building", "crown"))
REDUCTIONS = ("mean", "max", "sum_div128", "confidence_div128")


def feature_names():
    return tuple(f"physical.{side}.{kind}.{name}.{reduction}"
                 for side, _, kind in GROUPS for name in BODY_NAMES for reduction in REDUCTIONS)


def nearest_crown(raw, fc, crown, side):
    """Euclidean distance to a visible crown, with no inferred attacking target."""
    time = crown.shape[0]
    xy_known = np.minimum(fc[..., 0], fc[..., 1])
    selected = crown & (fc[..., side] > 0) & (raw[..., side] > .5) & (xy_known > 0)
    if (selected.sum(1) > 3).any():
        raise ValueError("more than three visible crowns on one side")
    positions = np.zeros((time, 3, 2), dtype=np.float32)
    confidence = np.zeros((time, 3), dtype=np.float32)
    rows, columns = np.nonzero(selected)
    slots = (selected.cumsum(1) - 1)[rows, columns]
    positions[rows, slots] = raw[rows, columns, :2]
    confidence[rows, slots] = np.minimum(xy_known[rows, columns], fc[rows, columns, side])
    xy = np.where((xy_known > 0)[..., None], raw[..., :2], 0)
    delta = (xy[:, :, None, :] - positions[:, None, :, :]) * np.array([18, 32], dtype=np.float32)
    distances = np.sqrt(np.square(delta).sum(-1))
    distances = np.where(confidence[:, None, :] > 0, distances, np.inf)
    best = distances.min(-1)
    # Equal-distance crowns use the strongest available observation, independent
    # of entity slot order. No crown has confidence zero.
    tied_confidence = np.where(distances == best[..., None], confidence[:, None, :], 0).max(-1)
    known = np.minimum(xy_known, tied_confidence)
    return np.where(known > 0, 1 / (1 + best), 0), known


def body_features(public, table):
    ids = np.asarray(public["entity_ids"])
    mask = np.asarray(public["entity_mask"], dtype=bool)
    if ids.ndim != 2 or mask.shape != ids.shape:
        raise ValueError("invalid body shape")
    time, entities = ids.shape
    ic = _confidence(public["entity_id_confidence"], ids.shape, "body identity confidence", mask)
    fc = _confidence(public["entity_feature_confidence"], (*ids.shape, 32),
                     "body field confidence", mask[..., None])
    _available(public["entity_features"], fc, "body fields")
    raw = np.where(fc > 0, public["entity_features"], 0).astype(np.float32)
    observed = ids[ic > 0]
    if (not np.isfinite(observed).all() or
            ((observed < 0) | (observed >= len(table.vocabulary)) | (observed != np.floor(observed))).any()):
        raise ValueError("visible body identity outside fixed vocabulary")
    tokens = np.where(ic > 0, ids, 0).astype(np.int64)
    troop = (raw[..., 4] > .5) & (fc[..., 4] > 0)
    building = (raw[..., 5] > .5) & (fc[..., 5] > 0)
    body = mask & (troop | building)
    known = body & table.resolved[tokens] & (ic > 0)
    for column, index in enumerate(STATIC_INDICES):
        available = known & (fc[..., index] > 0)
        if (raw[..., index][available] != table.expected_static[tokens, column][available]).any():
            raise ValueError("public body static field differs from frozen metadata")
    for index in (0, 1, 9, 10):
        available = body & (fc[..., index] > 0)
        if ((raw[..., index][available] < 0) | (raw[..., index][available] > 1)).any():
            raise ValueError("public body fraction outside unit interval")
    values = np.zeros((time, entities, len(BODY_NAMES)), dtype=np.float32)
    confidences = np.zeros_like(values)
    values[..., :8] = table.values[tokens]
    confidences[..., :8] = np.minimum(table.confidence[tokens], ic[..., None]) * known[..., None]

    def product(destination, left, right_value, right_confidence):
        values[..., destination] = values[..., left] * right_value
        confidences[..., destination] = np.minimum(confidences[..., left], right_confidence)

    product(8, 0, raw[..., 9], fc[..., 9])
    product(9, 7, raw[..., 10], fc[..., 10])
    product(10, 8, values[..., 3], confidences[..., 3])
    product(11, 1, values[..., 4], confidences[..., 4])
    product(12, 1, values[..., 6], confidences[..., 6])
    crown = building & known & np.isin(tokens, table.crown_ids)
    # Identity confidence also governs whether the object is known to be a crown.
    crown_fc = np.minimum(fc, ic[..., None])
    proximity = {side: nearest_crown(raw, crown_fc, crown, side) for side in (2, 3)}
    blocks = []
    for _, side, kind in GROUPS:
        same, other = proximity[side], proximity[5 - side]
        product(13, 1, *other)
        product(14, 8, *other)
        product(15, 11, *same)
        kind_mask = troop if kind == "troop" else (crown if kind == "crown" else building & ~crown)
        kind_index = 4 if kind == "troop" else 5
        selected = body & kind_mask & (raw[..., side] > .5) & (fc[..., side] > 0)
        group_confidence = np.minimum(fc[..., side], fc[..., kind_index])
        weight = np.minimum(confidences, group_confidence[..., None]) * selected[..., None]
        weighted = values * weight
        count = (weight > 0).sum(1)
        total = weighted.sum(1, dtype=np.float64)
        maximum = np.where(weight > 0, weighted, 0).max(1, initial=0)
        block = np.stack((total / np.maximum(count, 1), maximum, total / 128,
                          weight.sum(1, dtype=np.float64) / 128), axis=-1)
        blocks.append(block.reshape(time, -1))
    result = np.concatenate(blocks, axis=1).astype(np.float32)
    if result.shape != (time, len(feature_names())) or not np.isfinite(result).all():
        raise ValueError("invalid physical features")
    return result


def augmented_features(public, layout, table):
    return np.concatenate((numeric_features(public, layout), body_features(public, table)), axis=1)
