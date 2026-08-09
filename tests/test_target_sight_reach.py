import numpy as np
import pytest

import clasher.entities as entity_module


@pytest.mark.parametrize("add_collision_radius", [False, True])
@pytest.mark.parametrize("building_extension", [0, 250])
@pytest.mark.parametrize("crown_extension", [0, 1250, 2000])
def test_allocation_reduced_target_sight_reach_is_bit_exact(
    monkeypatch,
    add_collision_radius,
    building_extension,
    crown_extension,
):
    monkeypatch.setattr(
        entity_module,
        "ADD_CHARACTER_RANGE_TO_RADIUS",
        add_collision_radius,
    )
    monkeypatch.setattr(
        entity_module,
        "EXTRA_SIGHT_RANGE_TO_BUILDING",
        building_extension,
    )
    monkeypatch.setattr(
        entity_module,
        "EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS",
        crown_extension,
    )
    collision_radius = np.array([0.0, 0.3, 0.5, 1.25, 2.0], dtype=np.float64)
    is_building = np.array([False, False, True, True, True], dtype=np.bool_)
    is_crown = np.array([False, False, False, True, True], dtype=np.bool_)

    expected = entity_module._target_sight_reach_reference(
        5.5,
        collision_radius,
        is_building,
        is_crown,
    )
    actual = entity_module._target_sight_reach(
        5.5,
        collision_radius,
        is_building,
        is_crown,
    )

    np.testing.assert_array_equal(actual, expected)
    assert not np.shares_memory(actual, collision_radius)
