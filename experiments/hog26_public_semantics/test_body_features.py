from types import SimpleNamespace

import numpy as np
import pytest
from body_features import augmented_features, body_features, feature_names
from residual_features import make_layout, numeric_features


def fixture():
    f = np.zeros((3, 4, 32), dtype=np.float32)
    f[:, 0, [0, 1, 2, 4, 9]] = [.5, .5, 1, 1, .5]
    f[:, 1, [0, 1, 3, 5, 9]] = [.5, .8, 1, 1, 1]
    f[:, 2, [0, 1, 2, 5, 9]] = [.5, .2, 1, 1, 1]
    public = {"entity_ids": np.tile([2, 3, 3, 0], (3, 1)), "entity_features": f,
                  "entity_mask": np.tile([1, 1, 1, 0], (3, 1)),
                  "entity_id_confidence": np.ones((3, 4), dtype=np.float32),
                  "entity_feature_confidence": np.ones_like(f),
                  "hand_ids": np.zeros((3, 4), dtype=np.int64),
                  "hand_id_confidence": np.ones((3, 4), dtype=np.float32),
                  "global_features": np.zeros((3, 18), dtype=np.float32),
                  "global_feature_confidence": np.ones((3, 18), dtype=np.float32)}
    table = SimpleNamespace(vocabulary=tuple(str(i) for i in range(12)),
                            values=np.zeros((12, 8), dtype=np.float32),
                            confidence=np.zeros((12, 8), dtype=np.float32),
                            resolved=np.zeros(12, dtype=bool),
                            expected_static=np.zeros((12, 5), dtype=np.float32), crown_ids=(3, 4))
    table.values[2] = [.1, .1, .25, 0, 1, 1, 0, 0]
    table.values[3] = [.5, .2, .25, 0, 1, 1, 0, 0]
    table.confidence[2:4] = 1
    table.resolved[2:4] = True
    return public, table


def test_augmentation_preserves_numeric_prefix_and_causality():
    public, table = fixture()
    layout = make_layout(12, [0, *range(2, 10)])
    result = augmented_features(public, layout, table)
    assert result.shape == (3, 809)
    np.testing.assert_array_equal(result[:, :425], numeric_features(public, layout))
    prefix = {key: value[:2] for key, value in public.items()}
    np.testing.assert_array_equal(augmented_features(prefix, layout, table), result[:2])


def test_padding_and_unavailable_identity_do_not_supply_metadata():
    public, table = fixture()
    expected = body_features(public, table)
    public["entity_features"][:, 3] = np.nan
    public["entity_ids"][:, 3] = -999
    public["entity_feature_confidence"][:, 3] = np.nan
    np.testing.assert_array_equal(body_features(public, table), expected)
    public["entity_id_confidence"][:, 0] = 0
    result = body_features(public, table)
    assert not result[:, :64].any()


def test_public_static_disagreement_refuses():
    public, table = fixture()
    public["entity_features"][0, 0, 23] = .1
    with pytest.raises(ValueError, match="static field differs"):
        body_features(public, table)


def test_distance_tracks_visible_crown_and_missing_crown_is_unknown():
    public, table = fixture()
    column = feature_names().index("physical.own.troop.enemy_crown_dps_proximity.mean")
    expected = body_features(public, table)[:, column]
    public["entity_features"][:, 1, 1] = .6
    assert (body_features(public, table)[:, column] > expected).all()
    public["entity_mask"][:, 1] = 0
    result = body_features(public, table)
    assert not result[:, column:column + 4].any()


def test_unknown_body_keeps_semantics_unavailable():
    public, table = fixture()
    public["entity_ids"][:, 0] = 9
    assert not body_features(public, table)[:, :64].any()


def test_reordering_entities_does_not_change_features():
    public, table = fixture()
    expected = body_features(public, table)
    for key in list(public):
        if key.startswith("entity_"):
            public[key] = public[key][:, [2, 0, 3, 1]]
    np.testing.assert_array_equal(body_features(public, table), expected)


def test_equal_distance_crowns_are_independent_of_entity_order():
    public, table = fixture()
    public["entity_features"][:, 2] = public["entity_features"][:, 1]
    public["entity_feature_confidence"][:, 2, :2] = .25
    expected = body_features(public, table)
    for key in list(public):
        if key.startswith("entity_"):
            public[key] = public[key][:, [0, 2, 1, 3]]
    np.testing.assert_array_equal(body_features(public, table), expected)
