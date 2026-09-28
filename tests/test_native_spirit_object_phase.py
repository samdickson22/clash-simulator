import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("spirit", ["IceSpirit", "ElectroSpirit"])
def test_native_spirit_flight_does_not_steer_target_and_lands_after_movement(
    fast_path, spirit
):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_spirit_object_phase_15_535_86.json")
        .read_text()
    )
    case = next(case for case in reference["cases"] if case["spirit"] == spirit)
    expected = {row["tick"]: row for row in case["frames"]}
    battle = BattleState(fast_path=fast_path)
    knight = None
    carrier = None
    cannon = None
    commands = {
        0: [(0, "Cannon", Position(3.5, 13.5))],
        60: [(0, spirit, Position(3.5, 11.5)), (1, "Knight", Position(3.5, 18.5))],
    }
    while battle.tick < max(expected):
        for owner, card, position in commands.get(battle.tick, []):
            battle.players[owner].hand = [card]
            before = set(battle.entities)
            assert battle.deploy_card(owner, card, position)
            entity = battle.entities[(set(battle.entities) - before).pop()]
            if card == "Knight":
                knight = entity
            elif card == spirit:
                carrier = entity
            elif card == "Cannon":
                cannon = entity
        battle.step()
        if battle.tick not in expected:
            continue
        row = expected[battle.tick]
        assert [round(knight.position.x * 1000), round(knight.position.y * 1000)] == row["xy"], battle.tick
        assert knight.hitpoints == row["hp"], battle.tick
        assert (cannon.hitpoints if cannon.id in battle.entities else None) == row["cannon_hp"], battle.tick
        observed = row["spirit"]
        if observed is None:
            assert carrier.id not in battle.entities, battle.tick
        else:
            assert [round(carrier.position.x * 1000), round(carrier.position.y * 1000)] == observed["xy"], battle.tick
            assert bool(getattr(carrier, "_self_projectile_launched", False)) == observed["projectile"], battle.tick
            assert carrier.entity_kind == (2 if observed["projectile"] else 0), battle.tick
