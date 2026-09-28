"""Native Goblins retain in-range depleted locks for due and non-due cycles."""

import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.attack_clock import OrdinaryAttackClock
from clasher.battle import BattleState
from clasher.ordinary_combat_clock import publish

REFERENCES = json.loads(
    (Path(__file__).parent / "fixtures/native_melee_depleted_range_15_535_86.json")
    .read_text()
)["cases"]


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("reference", REFERENCES, ids=lambda r: r["name"])
def test_connected_goblin_keeps_cycle_after_earlier_ally_kill(fast_path, reference):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    mapping = {}
    for row in reference["units"]:
        name = "Goblins" if row["cardId"] == 26000002 else "Archers"
        battle._spawn_unit_at_position(
            Position(row["x"] / 1000, row["y"] / 1000), row["owner"],
            battle.card_loader.get_card(name),
            deploy_delay_override=0 if name == "Goblins" else 0.4,
            snap_to_valid=False,
        )
        entity = battle.entities[max(battle.entities)]
        entity.hitpoints = row["hp"]
        mapping[row["nativeObjectId"]] = entity
    for row in reference["units"]:
        if "timeline" not in row:
            continue
        entity = mapping[row["nativeObjectId"]]
        entity.target_id = mapping[row["target"]].id
        entity._last_combat_target_id = entity.target_id
        entity._attack_windup_active = True
        entity._ordinary_clock = OrdinaryAttackClock(
            1100, 500, hit_timeline_ms=row["timeline"], load_remaining_ms=row["load"],
        )
        publish(entity, entity._ordinary_clock)
    observer = mapping[reference["observer_id"]]
    target = battle.entities[observer.target_id]
    start = (observer.position.x, observer.position.y)
    if fast_path:
        battle._refresh_fast_path_caches()

    battle.step()

    assert not target.is_alive
    assert observer.target_id is None
    assert [
        observer._ordinary_clock.hit_timeline_ms,
        observer._ordinary_clock.load_remaining_ms,
        observer._ordinary_clock.finish_elapsed_ms,
    ] == reference["expected_clock"]
    assert (observer.position.x, observer.position.y) == start
