import numpy as np
import pytest

from clasher.rl.action_space import DiscreteTileActionSpace


class _MaskSource:
    def __init__(self, mask: np.ndarray) -> None:
        self.mask = mask

    def get_building_placement_blocked_mask_world(
        self, size_tiles: int
    ) -> np.ndarray:
        assert size_tiles == 3
        return self.mask

    def get_troop_placement_blocked_mask_world(
        self, mover_radius: float
    ) -> np.ndarray:
        assert mover_radius == 0.75
        return self.mask


@pytest.mark.parametrize("player_id", [0, 1])
def test_canonical_occupancy_gather_matches_world_tile_order(player_id):
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    world_mask = np.fromfunction(
        lambda y, x: (x + 3 * y) % 7 == 0,
        (32, 18),
        dtype=int,
    )
    source = _MaskSource(world_mask)
    world_xy = action_space._world_tile_xy_by_player[player_id]
    expected = np.fromiter(
        (
            bool(world_mask[int(world_y), int(world_x)])
            for world_x, world_y in world_xy
        ),
        dtype=np.bool_,
        count=len(world_xy),
    )

    building = action_space._building_placement_blocked_mask_canonical(
        source, player_id, 3
    )
    troop = action_space._troop_placement_blocked_mask_canonical(
        source, player_id, 0.75
    )

    np.testing.assert_array_equal(building, expected)
    np.testing.assert_array_equal(troop, expected)
    assert not np.shares_memory(building, world_mask)
    assert not np.shares_memory(troop, world_mask)
