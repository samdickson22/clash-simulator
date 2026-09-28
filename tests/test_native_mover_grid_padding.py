"""Native movement components expand indexed extents before ordered queries."""

import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.native_spatial import NativeAvoidanceGrid

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_mover_grid_padding_15_535_86.json")
    .read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
def test_native_knight_inherits_last_bucket_candidate_steering(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    entities = []
    for row in REFERENCE["rows"]:
        name = {"IceGolemite": "IceGolem", "Archer": "Archers"}.get(
            row["name"], row["name"]
        )
        battle._spawn_unit_at_position(
            Position(*(v / 1000 for v in row["indexed_xy"])),
            1 if name == "IceGolem" else 0,
            battle.card_loader.get_card(name),
            deploy_delay_override=row["deploy"], snap_to_valid=False,
        )
        entities.append(battle.entities[max(battle.entities)])
    battle._native_avoidance_grid = NativeAvoidanceGrid(battle.entities.values())
    for entity, row in zip(entities, REFERENCE["rows"]):
        entity.position = Position(*(v / 1000 for v in row["xy"]))
        entity._native_avoidance = row["avoidance"]
        entity._facing_x_units, entity._facing_y_units = row["facing"]
        if row["name"] == "IceGolemite":
            entity._movement_target_id = -1
    knight = entities[-1]

    knight._update_native_avoidance(battle)

    assert knight._native_avoidance == REFERENCE["expected"]
