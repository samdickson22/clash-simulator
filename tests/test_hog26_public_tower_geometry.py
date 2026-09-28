import numpy as np

from scripts.hog26_public_tower_geometry import tower_geometry_features


def inputs():
    ids = np.array([[1, 2, 0]])
    entity = np.zeros((1, 3, 32), dtype=np.float32)
    entity[0, 0, [0, 1, 3, 4, 9]] = [4 / 18, 3 / 32, 1, 1, 1]
    entity[0, 1, [0, 1, 2, 4, 9]] = [4 / 18, 3 / 32, 1, 1, 1]
    mask = np.array([[True, True, False]])
    public = np.zeros((1, 18), dtype=np.float32)
    public[:, 8:14] = 1
    stats = np.zeros((3, 16), dtype=np.float32)
    stats[1:, 6] = np.log1p(100) / 8
    stats[1:, 7] = 1 / 12
    stats[1:, 14] = 1
    xy = np.array([[3, 3], [14, 3], [9, 1], [3, 29], [14, 29], [9, 31]])
    return ids, entity, mask, public, stats, xy, np.zeros(6), np.full(6, 1000), []


def test_geometry_uses_units_and_opposing_visible_attackers():
    result = tower_geometry_features(*inputs()).reshape(6, 8)
    np.testing.assert_allclose(result[0, 1], 0, atol=1e-6)
    np.testing.assert_allclose(result[0, 3:6], .1, rtol=1e-5)
    assert result[0, 6] == 1 / 8


def test_permutation_and_masked_entities_do_not_change_result():
    args = list(inputs())
    expected = tower_geometry_features(*args)
    args[1][0, 2] = 100
    np.testing.assert_array_equal(tower_geometry_features(*args), expected)
    for index in [0, 1, 2]:
        args[index] = args[index][:, [2, 0, 1]]
    np.testing.assert_allclose(tower_geometry_features(*args), expected)


def test_destroyed_tower_and_empty_attackers_are_finite():
    args = list(inputs())
    args[2][:] = False
    args[3][:, 8] = 0
    result = tower_geometry_features(*args).reshape(6, 8)
    assert np.isfinite(result).all()
    np.testing.assert_array_equal(result[0], 0)
    np.testing.assert_array_equal(result[1:, 2:], 0)


def test_reach_uses_target_radius_without_attacker_radius():
    args = list(inputs())
    args[1][0, 0, 0] = 5 / 18
    args[4][1, 12] = 1
    # Distance two tiles exceeds range one, regardless of attacker size.
    assert tower_geometry_features(*args).reshape(6, 8)[0, 6] == 0
    args[6][0] = 1
    assert tower_geometry_features(*args).reshape(6, 8)[0, 6] == 1 / 8


def test_unconsumed_entity_fields_cannot_change_geometry():
    args = list(inputs())
    expected = tower_geometry_features(*args)
    unused = sorted(set(range(32)) - {0, 1, 2, 4, 5, 9})
    args[1][..., unused] = 99
    np.testing.assert_array_equal(tower_geometry_features(*args), expected)
