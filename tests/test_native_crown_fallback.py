"""Native fallback placements straddle the surviving Princess Tower's lane."""

import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_crown_fallback_15_535_86.json")
    .read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: str(c["x"]))
def test_native_crown_fallback_after_one_princess_is_destroyed(fast_path, case):
    battle = BattleState(fast_path=fast_path)
    towers = {(e["owner"], e["x"], e["y"]): e for e in case["towers"]}
    for tower in list(battle.entities.values()):
        key = tower.player_id, round(tower.position.x * 1000), round(tower.position.y * 1000)
        if key not in towers:
            tower.take_damage(tower.hitpoints)
        else:
            tower.hitpoints = towers[key]["hp"]
    battle._cleanup_dead_entities()
    battle._spawn_unit_at_position(
        Position(*(v / 1000 for v in case["xy"])), case["owner"],
        battle.card_loader.get_card("IceGolem"),
        deploy_delay_override=0, snap_to_valid=False,
    )
    golem = battle.entities[max(battle.entities)]
    if fast_path:
        battle._refresh_fast_path_caches()

    target = golem.get_nearest_target(battle.entities)

    assert [round(target.position.x * 1000), round(target.position.y * 1000)] == case["expected_target_xy"]


def test_deployed_clock_matches_native_first_active_tick_and_half_second():
    battle = BattleState()
    battle._spawn_unit_at_position(
        Position(14.5, 18.5), 1, battle.card_loader.get_card("IceGolem"),
        deploy_delay_override=1, snap_to_valid=False,
    )
    golem = battle.entities[max(battle.entities)]
    battle.step(20)
    assert golem._native_deployed_elapsed_ms == 0
    battle.step()
    assert golem._native_deployed_elapsed_ms == 50
    battle.step(9)
    assert golem._native_deployed_elapsed_ms == 500


def test_idle_fast_forward_preserves_deployed_clock_for_all_crowns():
    regular, fast = BattleState(), BattleState()
    regular.step(11)
    assert fast.fast_forward_idle_ticks(11) == 11
    assert [e._native_deployed_elapsed_ms for e in regular.entities.values()] == [
        e._native_deployed_elapsed_ms for e in fast.entities.values()
    ] == [550] * 6
