import numpy as np
import pytest
from scalar_features import build_game_features, feature_names


def fixture(t=24, n=5):
    x = {
        'entity_ids': np.full((t, n), 3, dtype=np.int64),
        'entity_features': np.zeros((t, n, 32), dtype=np.float32),
        'entity_mask': np.ones((t, n), dtype=bool),
        'entity_id_confidence': np.ones((t, n), dtype=np.float32),
        'entity_feature_confidence': np.ones((t, n, 32), dtype=np.float32),
        'hand_ids': np.tile(np.arange(3, 7), (t, 1)),
        'hand_id_confidence': np.ones((t, 4), dtype=np.float32),
        'global_features': np.arange(t * 18, dtype=np.float32).reshape(t, 18) / 500,
        'global_feature_confidence': np.ones((t, 18), dtype=np.float32),
        'vocabulary_size': 8,
    }
    x['entity_features'][..., :2] = .2
    x['entity_features'][..., 2] = 1
    x['entity_features'][..., 4] = 1
    x['entity_features'][..., 9] = np.arange(n) / max(n, 1)
    return x


def test_exact_order_and_count():
    names = feature_names(8)
    assert len(names) == 8 * 37 + 36 + 4 * 8 + 54 + 3
    assert names[:5] == ('own.troop.count', 'own.troop.feature0.mean', 'own.troop.feature0.max', 'own.troop.feature1.mean', 'own.troop.feature1.max')
    assert len(set(names)) == len(names)
    assert names[-3:] == ('lag1.available', 'lag5.available', 'lag20.available')
    x = fixture()
    result = build_game_features(**x)
    assert result.dtype == np.float32
    assert result[0, names.index('own.troop.count')] == 5
    assert result[0, names.index('own.troop.feature9.mean')] == pytest.approx(.4)
    assert result[0, names.index('own.troop.feature9.max')] == pytest.approx(.8)
    assert result[0, names.index('own.troop.cell0_0.count')] == 5
    assert result[0, names.index('enemy.troop.count')] == 0
    assert result[0, names.index('hand0.token3')] == 1


def test_entity_permutation_and_padding_invariance():
    x = fixture()
    expected = build_game_features(**x)
    y = dict(x)
    for key in x:
        if key.startswith('entity_'):
            y[key] = x[key][:, [4, 2, 1, 0, 3]]
    np.testing.assert_array_equal(expected, build_game_features(**y))
    for key in x:
        if key.startswith('entity_'):
            padding = np.zeros_like(x[key][:, :2])
            if key not in ('entity_mask', 'entity_ids'):
                padding[:] = np.nan
            y[key] = np.concatenate((x[key], padding), axis=1)
    np.testing.assert_array_equal(expected, build_game_features(**y))


def test_future_causality_and_game_reset():
    x = fixture()
    expected = build_game_features(**x)
    y = {k: v.copy() if isinstance(v, np.ndarray) else v for k, v in x.items()}
    y['global_features'][10:] = -10
    y['entity_features'][10:, :, 9] = 1
    np.testing.assert_array_equal(expected[:10], build_game_features(**y)[:10])
    prefix = {k: v[:10] if isinstance(v, np.ndarray) else v for k, v in x.items()}
    np.testing.assert_array_equal(expected[:10], build_game_features(**prefix))
    second = {k: v[10:] if isinstance(v, np.ndarray) else v for k, v in x.items()}
    reset = build_game_features(**second)
    names = feature_names(8)
    assert reset[0, names.index('lag1.available')] == 0
    assert reset[0, names.index('lag1.global0.difference')] == 0
    assert expected[10, names.index('lag1.available')] == 1


def test_zero_availability_ignores_unknown_values():
    x = fixture(t=1)
    for key in ('entity_feature_confidence', 'entity_id_confidence', 'global_feature_confidence', 'hand_id_confidence'):
        x[key][:] = 0
    for key in ('entity_features', 'global_features'):
        x[key][:] = np.nan
    x['entity_ids'][:] = -900
    x['hand_ids'][:] = -900
    np.testing.assert_array_equal(build_game_features(**x), 0)


def test_per_feature_available_reductions_and_negative_max():
    x = fixture(t=1, n=3)
    x['entity_features'][0, :, 9] = [-.8, -.2, np.nan]
    x['entity_feature_confidence'][0, :, 9] = [1, .5, 0]
    result = build_game_features(**x)
    names = feature_names(8)
    assert result[0, names.index('own.troop.feature9.mean')] == pytest.approx(-.45)
    assert result[0, names.index('own.troop.feature9.max')] == pytest.approx(-.1)


def test_lags_and_joint_availability():
    x = fixture()
    result = build_game_features(**x)
    names = feature_names(8)
    for lag in (1, 5, 20):
        col = names.index(f'lag{lag}.global0.difference')
        np.testing.assert_array_equal(result[:lag, col], 0)
        assert result[lag, col] == pytest.approx(18 * lag / 500)
    x['global_feature_confidence'][0, 0] = 0
    result = build_game_features(**x)
    for lag in (1, 5, 20):
        assert result[lag, names.index(f'lag{lag}.global0.difference')] == 0
        assert result[lag, names.index(f'lag{lag}.available')] == 1


def test_all_groups_and_arena_boundary():
    x = fixture(t=1, n=8)
    f = x['entity_features']
    f[..., 2:8] = 0
    for i in range(8):
        f[0, i, 2 + i // 4] = 1
        f[0, i, 4 + i % 4] = 1
    f[..., :2] = 1
    result = build_game_features(**x)
    names = feature_names(8)
    for side in ('own', 'enemy'):
        for kind in ('troop', 'building', 'projectile', 'effect'):
            assert result[0, names.index(f'{side}.{kind}.count')] == 1
            assert result[0, names.index(f'{side}.{kind}.cell3_3.count')] == 1


def test_no_identity_ordinal_and_ordered_hand():
    x = fixture(t=1)
    baseline = build_game_features(**x)
    x['entity_ids'][:] = 7
    np.testing.assert_array_equal(baseline, build_game_features(**x))
    x['hand_ids'] = x['hand_ids'][:, ::-1]
    assert not np.array_equal(baseline, build_game_features(**x))
    x['hand_id_confidence'][0, 0] = .25
    names = feature_names(8)
    assert build_game_features(**x)[0, names.index('hand0.token6')] == .25


@pytest.mark.parametrize('mutation', ['hand', 'confidence', 'position', 'global'])
def test_invalid_available_inputs_reject(mutation):
    x = fixture()
    if mutation == 'hand':
        x['hand_ids'][0, 0] = 99
    elif mutation == 'confidence':
        x['entity_feature_confidence'][0, 0, 0] = np.nan
    elif mutation == 'position':
        x['entity_features'][0, 0, 0] = 1.1
    else:
        x['global_features'][0, 0] = np.nan
    with pytest.raises(ValueError):
        build_game_features(**x)
