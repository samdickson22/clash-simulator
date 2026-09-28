"""An in-range live replacement preserves the established ordinary hit."""

import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.attack_clock import OrdinaryAttackClock
from clasher.battle import BattleState
from clasher.ordinary_combat_clock import publish

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_live_retarget_15_535_86.json")
    .read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
def test_knight_preserves_hit_when_switching_to_live_goblin_in_reach(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    mapping = {}
    for row in REFERENCE["bodies"]:
        name = "Knight" if row["cardId"] == 26000000 else "Goblins"
        battle._spawn_unit_at_position(
            Position(row["x"] / 1000, row["y"] / 1000), row["owner"],
            battle.card_loader.get_card(name),
            deploy_delay_override=0 if name == "Knight" else 0.5,
            snap_to_valid=False,
        )
        entity = battle.entities[max(battle.entities)]
        entity.hitpoints = row["hp"]
        mapping[row["nativeObjectId"]] = entity
    knight = mapping[5000055]
    old = mapping[REFERENCE["old_target_id"]]
    replacement = mapping[REFERENCE["new_target_id"]]
    knight.target_id = old.id
    knight._last_combat_target_id = old.id
    knight._attack_windup_active = True
    knight._ordinary_clock = OrdinaryAttackClock(
        1200, 700, hit_timeline_ms=REFERENCE["initial_clock"][0],
        load_remaining_ms=REFERENCE["initial_clock"][1],
    )
    publish(knight, knight._ordinary_clock)
    if fast_path:
        battle._refresh_fast_path_caches()

    battle.step()

    assert old.is_alive and replacement.is_alive
    assert knight.target_id == replacement.id
    assert [knight._ordinary_clock.hit_timeline_ms,
            knight._ordinary_clock.load_remaining_ms] == REFERENCE["expected_after_one"]
    for _ in range(REFERENCE["expected_hit_step"] - 2):
        battle.step()
        assert replacement.is_alive
    battle.step()
    assert not replacement.is_alive
    assert old.is_alive
