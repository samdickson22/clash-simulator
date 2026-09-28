import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building


@pytest.mark.parametrize("fast_path", [False, True])
def test_native_tesla_deployment_combat_precedes_lifetime_decay(fast_path):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_tesla_deploy_combat_15_535_86.json")
        .read_text()
    )
    expected = {row["elapsed_tick"]: row for row in reference["frames"]}
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    tesla = battle._spawn_entity(
        Building, Position(9.0, 10.0), 0, battle.card_loader.get_card("Tesla")
    )
    target_id = battle.next_entity_id
    battle._spawn_unit_at_position(
        Position(9.0, 14.0), 1, battle.card_loader.get_card("Knight")
    )
    battle.entities[target_id].apply_stun(99.0)
    while battle.tick < max(expected):
        battle.step()
        if battle.tick in expected:
            row = expected[battle.tick]
            assert tesla.hitpoints == row["hp"]
            assert (tesla.target_id is not None) == row["target_present"]
            if row["attack_remaining"] is not None:
                assert tesla.attack_cooldown == pytest.approx(row["attack_remaining"])


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("stunned_at_acquisition", [False, True])
def test_native_tesla_finish_to_acquisition_load(fast_path, stunned_at_acquisition):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_tesla_acquisition_load_15_535_86.json")
        .read_text()
    )
    native = {frame["tick"]: frame["rows"][0] for frame in reference["frames"]}
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    tesla = battle._spawn_entity(
        Building, Position(9.0, 10.0), 0, battle.card_loader.get_card("Tesla")
    )
    tesla.deploy_delay_remaining = 0.0
    tesla.placement_pending = False
    battle._spawn_unit_at_position(
        Position(9.0, 14.0), 1, battle.card_loader.get_card("Knight")
    )
    # Reconstruct the observed post-kill attacker state at native837.
    tesla.attack_cooldown = native[837]["hit_speed"] / 1000.0
    tesla._attack_finish_elapsed_ms = native[837]["finish"]
    tesla._last_combat_target_id = None
    tesla._has_attacked_once = True
    for _ in range(5):
        tesla.update_combat_component(battle.dt, battle)
    assert tesla._attack_finish_elapsed_ms == native[842]["finish"] == 0
    remaining_before_acquisition = (
        native[842]["load"] / 1000.0 + tesla.get_preloaded_attack_time_seconds()
    )
    assert tesla.attack_cooldown == pytest.approx(remaining_before_acquisition)

    if stunned_at_acquisition:
        tesla.stun_timer = 1.0
    tesla.update_combat_component(battle.dt, battle)
    assert tesla.target_id is not None
    expected = (
        remaining_before_acquisition
        if stunned_at_acquisition
        else (native[843]["hit_speed"] - native[843]["timeline"]) / 1000.0
    )
    assert tesla.attack_cooldown == pytest.approx(expected)
