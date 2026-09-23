from __future__ import annotations

import copy

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Entity, Troop
from clasher.kinematics import logic_units_to_tiles, tiles_to_logic_units


def _reference(entity: Entity) -> None:
    entity.position.x = logic_units_to_tiles(tiles_to_logic_units(entity.position.x))
    entity.position.y = logic_units_to_tiles(tiles_to_logic_units(entity.position.y))


@pytest.mark.parametrize(
    "value",
    [
        -1000.0005,
        -31.9995,
        -0.0015,
        -0.0005,
        -0.0,
        0.0,
        0.0005,
        0.0015,
        3.499499999999,
        3.4995,
        17.9995,
        31.9995,
        1000.0005,
    ],
)
def test_inline_position_quantization_matches_helpers(value: float) -> None:
    source = BattleState(fast_path=True)
    stats = source.card_loader.get_card("Knight")
    assert stats is not None
    entity = source._spawn_entity(Troop, Position(value, -value), 0, stats)
    expected = copy.deepcopy(entity)

    _reference(expected)
    entity.quantize_logic_position()

    assert entity.position.x == expected.position.x
    assert entity.position.y == expected.position.y
