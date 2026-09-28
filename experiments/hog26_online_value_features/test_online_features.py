"""Stream/batch parity, masked history ownership, reset and transactional refusal."""

from types import SimpleNamespace

import numpy as np
import pytest
from body_features import augmented_features
from body_features import feature_names as physical_names
from health_features import augment
from health_features import make_layout as health_layout
from online_features import PublicFeatureState
from residual_features import make_layout


def fixture():
    n, entities, vocabulary = 64, 4, 12
    rng = np.random.default_rng(31)
    public = {'entity_ids': np.tile([2, 3, 3, 0], (n, 1)),
              'entity_features': np.zeros((n, entities, 32), np.float32),
              'entity_mask': np.tile([1, 1, 1, 0], (n, 1)),
              'entity_id_confidence': np.ones((n, entities), np.float32),
              'entity_feature_confidence': np.ones((n, entities, 32), np.float32),
              'hand_ids': np.zeros((n, 4), np.int64), 'hand_id_confidence': np.ones((n, 4), np.float32),
              'global_features': rng.uniform(0, 1, (n, 18)).astype(np.float32),
              'global_feature_confidence': np.ones((n, 18), np.float32)}
    public['global_features'][:, 0] = np.arange(n, dtype=np.float32) / 1000
    public['global_features'][:, 8:14] = .95 - np.arange(n, dtype=np.float32)[:, None] / 1000
    public['global_feature_confidence'][::3, 6] = 0
    public['global_features'][::3, 6] = np.nan
    public['global_feature_confidence'][::2, 2] = .5
    f = public['entity_features']
    f[:, 0, [0, 1, 2, 4, 9]] = [.5, .5, 1, 1, .5]
    f[:, 1, [0, 1, 3, 5, 9]] = [.5, .8, 1, 1, 1]
    f[:, 2, [0, 1, 2, 5, 9]] = [.5, .2, 1, 1, 1]
    table = SimpleNamespace(vocabulary=tuple(str(i) for i in range(vocabulary)), values=np.zeros((vocabulary, 8), np.float32),
                            confidence=np.zeros((vocabulary, 8), np.float32), resolved=np.zeros(vocabulary, bool),
                            expected_static=np.zeros((vocabulary, 5), np.float32), crown_ids=(3, 4))
    table.values[2:4] = [.1, .1, .25, 0, 1, 1, 0, 0]
    table.confidence[2:4] = 1
    table.resolved[2:4] = True
    layout = make_layout(vocabulary, (0, *range(2, 10)))
    expected = augment(augmented_features(public, layout, table), health_layout((*layout.names, *physical_names())))
    return public, layout, table, expected


def frame(public, row):
    return {key: value[row].copy() for key, value in public.items()}


def test_complete_stream_matches_batch_and_bounds_history():
    public, layout, table, expected = fixture()
    state = PublicFeatureState(layout, table)
    actual = np.stack([state.step(frame(public, i)) for i in range(64)])
    assert actual.dtype == expected.dtype and actual.tobytes() == expected.tobytes()
    assert state.seen == 64 and state.history_frames == 20
    state.reset()
    np.testing.assert_array_equal(state.step(frame(public, 0)), expected[0])


def test_clone_and_input_ownership():
    public, layout, table, expected = fixture()
    state = PublicFeatureState(layout, table)
    consumed = []
    for i in range(20):
        row = frame(public, i)
        state.step(row)
        consumed.append(row)
    clone = state.clone()
    consumed[0]['global_features'][2] = -100
    different = frame(public, 20)
    different['global_features'][2] = 1 - different['global_features'][2]
    clone.step(different)
    np.testing.assert_array_equal(state.step(frame(public, 20)), expected[20])
    parent = state.step(frame(public, 21))
    branch = clone.step(frame(public, 21))
    np.testing.assert_array_equal(parent, expected[21])
    assert not np.array_equal(parent, branch)


def test_invalid_observations_do_not_advance_state():
    public, layout, table, expected = fixture()
    state = PublicFeatureState(layout, table)
    with pytest.raises(ValueError, match='complete public prefix'):
        state.step(frame(public, 1))
    row = frame(public, 0)
    with pytest.raises(ValueError, match='exact public fields'):
        state.step({**row, 'target_margin': .2})
    state.step(row)
    with pytest.raises(ValueError, match='strictly increasing'):
        state.step(row)
    bad = frame(public, 1)
    bad['entity_features'][0, 23] = .5
    with pytest.raises(ValueError, match='static field differs'):
        state.step(bad)
    assert state.seen == 1
    np.testing.assert_array_equal(state.step(frame(public, 1)), expected[1])


def test_optional_next_card_cannot_change_features():
    public, layout, table, expected = fixture()
    state = PublicFeatureState(layout, table)
    row = frame(public, 0)
    row['hand_ids'] = np.r_[row['hand_ids'], 999999]
    row['hand_id_confidence'] = np.r_[row['hand_id_confidence'], np.nan]
    np.testing.assert_array_equal(state.step(row), expected[0])
