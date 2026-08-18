from __future__ import annotations

import copy
from typing import Any, cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.torch_sim.passive_mechanics import (
    STEALTH_FOREVER_MS,
    PassiveEventOpcode,
)
from clasher.torch_sim.resident_stealth import TensorResidentStealth
from clasher.torch_sim.runtime_state import TensorBattleRuntime


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _spawn_troop(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    battle._spawn_unit_at_position(
        position,
        player,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    entity = battle.entities[battle.next_entity_id - 1]
    assert isinstance(entity, Troop)
    entity.position = Position(position.x, position.y)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    return entity


def _tesla_battle() -> tuple[BattleState, Building, Troop]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Tesla")
    assert stats is not None
    tesla = battle._spawn_entity(Building, Position(9.0, 12.0), 0, stats)
    assert isinstance(tesla, Building)
    tesla_value = cast(Any, tesla)
    tesla.deploy_delay_remaining = 0.0
    tesla.placement_pending = False
    tesla.on_spawn()
    target = _spawn_troop(battle, "Knight", 1, Position(9.0, 25.0))
    tesla.attack_cooldown = 0.73
    tesla_value.movement_speed = 0.0
    return battle, tesla, target


def _ghost_battle() -> tuple[BattleState, Troop, Troop]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    ghost = _spawn_troop(battle, "RoyalGhost", 0, Position(9.0, 12.0))
    enemy = _spawn_troop(battle, "Knight", 1, Position(9.0, 13.1))
    ghost.target_id = enemy.id
    enemy.target_id = ghost.id
    ghost.attack_cooldown = 0.61
    return battle, ghost, enemy


def _stack(
    battles: list[BattleState],
    device: str,
) -> tuple[TensorBattleRuntime, TensorResidentStealth]:
    runtime = TensorBattleRuntime.from_battles(
        [copy.deepcopy(battle) for battle in battles],
        device=device,
        max_entities=8,
        event_capacity=64,
    )
    return runtime, TensorResidentStealth.from_battles(runtime, battles)


def _slot(runtime: TensorBattleRuntime, row: int, entity_id: int) -> int:
    return runtime.battle.entity_id[row].tolist().index(entity_id)


def _mechanic(entity: Troop | Building, name: str) -> Any:
    return next(
        mechanic for mechanic in entity.mechanics if type(mechanic).__name__ == name
    )


def test_tesla_idle_hide_reveal_freeze_speed_and_eligibility_are_exact(
    tensor_device: str,
) -> None:
    battle, tesla, target = _tesla_battle()
    runtime, owner = _stack([battle], tensor_device)
    tesla_slot = _slot(runtime, 0, tesla.id)
    target_slot = _slot(runtime, 0, target.id)
    mechanic = _mechanic(tesla, "HideWhenIdle")
    tesla_value = cast(Any, tesla)
    original_attack_clock = tesla.attack_cooldown
    original_movement_speed = tesla_value.movement_speed
    timeline = (
        (400, False, False, 1.0, 1.0),
        (399, False, False, 1.0, 1.0),
        (1, False, False, 1.0, 1.0),
        (50, True, True, 1.0, 1.0),
        (50, True, False, 1.0, 1.0),
        (750, True, False, 1.0, 1.0),
        (800, False, False, 0.5, 2.0),
    )
    transition_opcodes: list[int] = []
    for dt_ms, nearby, stunned, slow, buff in timeline:
        target.position = Position(9.0, 13.0) if nearby else Position(9.0, 25.0)
        runtime.battle.entity_y_units[0, target_slot] = round(target.position.y * 1_000)
        tesla.stun_timer = 1.0 if stunned else 0.0
        tesla.slow_multiplier = slow
        tesla.movement_speed_buff_multiplier = buff
        runtime.battle.tick_milliseconds[0] = dt_ms
        runtime.status.stun_timer[0, tesla_slot] = tesla.stun_timer
        runtime.status.slow_multiplier[0, tesla_slot] = slow
        runtime.status.movement_speed_buff_multiplier[0, tesla_slot] = buff

        mechanic.on_object_tick(tesla, dt_ms)
        result = owner.step_(runtime)

        assert result.committed.tolist() == [True]
        assert runtime.battle.rng.python_state(0) == battle.rng.getstate()
        assert runtime.events.count.tolist() == [0]
        assert owner.state.hide_phase_ms[0, tesla_slot].item() == pytest.approx(
            mechanic._phase_ms
        )
        assert owner.state.hidden_building[0, tesla_slot].item() is bool(
            tesla_value._hidden_building
        )
        assert result.combat_blocked[0, tesla_slot].item() is bool(
            tesla_value._hidden_building
        )
        assert result.movement_blocked[0, tesla_slot].item() is bool(
            tesla_value._hidden_building
        )
        assert result.targetable[0, tesla_slot].item() is (
            not tesla_value._hidden_building
        )
        assert result.effect_receivable[0, tesla_slot].item() is (
            not tesla_value._hidden_building
        )
        assert result.area_receivable_affects_hidden[0, tesla_slot].item()
        transition_opcodes.extend(result.object_events.opcode.tolist())

    assert transition_opcodes == [
        int(PassiveEventOpcode.HIDDEN),
        int(PassiveEventOpcode.REVEALED),
        int(PassiveEventOpcode.HIDDEN),
    ]
    assert tesla.attack_cooldown == original_attack_clock
    assert tesla_value.movement_speed == original_movement_speed
    assert runtime.phases.target_slot[0, tesla_slot].item() == -1


def test_royal_ghost_attack_melee_hold_exact_fade_and_lock_cancellation(
    tensor_device: str,
) -> None:
    battle, ghost, enemy = _ghost_battle()
    runtime, owner = _stack([battle], tensor_device)
    ghost_slot = _slot(runtime, 0, ghost.id)
    enemy_slot = _slot(runtime, 0, enemy.id)
    mechanic = _mechanic(ghost, "InvisibilityWhenNotAttacking")
    initial_attack_clock = ghost.attack_cooldown

    assert owner.state.stealth_until_ms[0, ghost_slot].item() == STEALTH_FOREVER_MS
    mechanic.on_attack_start(ghost, enemy)
    mechanic.on_object_tick(ghost, 50)
    runtime.battle.tick_milliseconds[0] = 50
    attacks = torch.zeros_like(runtime.entity_pool.active)
    attacks[0, ghost_slot] = True
    visible = owner.step_(runtime, attack_started=attacks)

    assert visible.committed.tolist() == [True]
    assert runtime.battle.rng.python_state(0) == battle.rng.getstate()
    assert visible.combat_events.opcode.tolist() == [int(PassiveEventOpcode.VISIBLE)]
    assert owner.state.fade_elapsed_ms[0, ghost_slot].item() == 0.0
    assert owner.state.stealth_until_ms[0, ghost_slot].item() == 0
    assert visible.targetable[0, ghost_slot].item()
    assert not visible.combat_blocked[0, ghost_slot].item()

    ghost.stun_timer = 3.0
    runtime.status.stun_timer[0, ghost_slot] = 3.0
    mechanic.on_object_tick(ghost, mechanic.fade_delay_ms + 50)
    runtime.battle.tick_milliseconds[0] = mechanic.fade_delay_ms + 50
    held = owner.step_(runtime)
    assert held.committed.tolist() == [True]
    assert runtime.battle.rng.python_state(0) == battle.rng.getstate()
    assert owner.state.fade_elapsed_ms[0, ghost_slot].item() == 0.0
    assert owner.state.stealth_until_ms[0, ghost_slot].item() == 0

    ghost.target_id = None
    enemy.position = Position(9.0, 25.0)
    runtime.battle.entity_y_units[0, enemy_slot] = 25_000
    owner.combat_target_entity_id[0, ghost_slot] = 0
    owner.state.target_slot[0, ghost_slot] = -1
    runtime.phases.target_slot[0, ghost_slot] = -1
    runtime.battle.tick_milliseconds[0] = 50
    for _ in range(39):
        mechanic.on_object_tick(ghost, 50)
        result = owner.step_(runtime)
        assert result.committed.tolist() == [True]
        assert runtime.battle.rng.python_state(0) == battle.rng.getstate()
    assert mechanic.time_since_attack_ms == 1_950.0
    assert owner.state.fade_elapsed_ms[0, ghost_slot].item() == 1_950.0
    assert owner.state.stealth_until_ms[0, ghost_slot].item() == 0

    mechanic.on_object_tick(ghost, 50)
    invisible = owner.step_(runtime)
    assert not invisible.target_cancelled[0, enemy_slot].item()
    assert owner.combat_target_entity_id[0, enemy_slot].item() == ghost.id
    assert runtime.phases.target_slot[0, enemy_slot].item() == ghost_slot
    enemy.update_combat_component(battle.dt, battle)
    lock_result = owner.validate_combat_locks_(runtime)

    assert owner.state.fade_elapsed_ms[0, ghost_slot].item() == 2_000.0
    assert owner.state.stealth_until_ms[0, ghost_slot].item() == STEALTH_FOREVER_MS
    assert invisible.object_events.opcode.tolist() == [
        int(PassiveEventOpcode.INVISIBLE)
    ]
    assert not invisible.targetable[0, ghost_slot].item()
    assert invisible.secondary_targetable[0, ghost_slot].item()
    assert invisible.effect_receivable[0, ghost_slot].item()
    assert invisible.area_receivable[0, ghost_slot].item()
    assert lock_result.committed.tolist() == [True]
    assert lock_result.target_cancelled[0, enemy_slot].item()
    assert owner.combat_target_entity_id[0, enemy_slot].item() == 0
    assert runtime.phases.target_slot[0, enemy_slot].item() == -1
    assert enemy.target_id != ghost.id
    assert ghost.attack_cooldown == initial_attack_clock
    assert runtime.events.count.tolist() == [0]


def test_deployment_gates_idle_clock_but_zero_crossing_ticks_character(
    tensor_device: str,
) -> None:
    battle, ghost, enemy = _ghost_battle()
    mechanic = _mechanic(ghost, "InvisibilityWhenNotAttacking")
    mechanic.time_since_attack_ms = 0.0
    cast(Any, ghost)._stealth_until = 0
    ghost.target_id = None
    enemy.position = Position(9.0, 25.0)
    ghost.deploy_delay_remaining = 0.05
    ghost.placement_pending = True
    runtime, owner = _stack([battle], tensor_device)
    ghost_slot = _slot(runtime, 0, ghost.id)
    runtime.battle.tick_milliseconds[0] = 50

    blocked = owner.step_(runtime)
    assert blocked.committed.tolist() == [True]
    assert owner.state.fade_elapsed_ms[0, ghost_slot].item() == 0.0

    ghost.deploy_delay_remaining = 0.0
    ghost.placement_pending = False
    runtime.battle.entity_deploy_delay[0, ghost_slot] = 0.0
    runtime.battle.entity_placement_pending[0, ghost_slot] = False
    mechanic.on_object_tick(ghost, 50)
    crossed = owner.step_(runtime)
    assert crossed.committed.tolist() == [True]
    assert owner.state.fade_elapsed_ms[0, ghost_slot].item() == 50.0
    assert mechanic.time_since_attack_ms == 50.0


def test_clone_fork_reset_and_mixed_identity_rollback_are_atomic() -> None:
    left, left_tesla, _ = _tesla_battle()
    right, right_tesla, _ = _tesla_battle()
    runtime, owner = _stack([left, right], "cpu")
    left_slot = _slot(runtime, 0, left_tesla.id)
    right_slot = _slot(runtime, 1, right_tesla.id)
    before = owner.clone()
    before_targets = runtime.phases.target_slot.clone()
    runtime.battle.entity_id[1, right_slot] += 100
    runtime.battle.tick_milliseconds[:] = 800

    result = owner.step_(runtime)

    assert result.committed.tolist() == [True, False]
    assert owner.state.hidden_building[0, left_slot].item()
    assert torch.equal(owner.state.hidden_building[1], before.state.hidden_building[1])
    assert torch.equal(runtime.phases.target_slot[1], before_targets[1])

    clone = owner.clone()
    clone.state.hide_phase_ms[0, left_slot] = 17.0
    assert owner.state.hide_phase_ms[0, left_slot].item() != 17.0
    fork = clone.fork([0])
    assert fork.state.hide_phase_ms[0, left_slot].item() == 17.0
    clone.reset_rows_([0], owner, [0])
    assert clone.state.hide_phase_ms[0, left_slot].item() == (
        owner.state.hide_phase_ms[0, left_slot].item()
    )


def test_catalog_support_is_mechanic_opcode_driven() -> None:
    tesla_battle, tesla, _ = _tesla_battle()
    ghost_battle, ghost, _ = _ghost_battle()
    runtime, owner = _stack([tesla_battle, ghost_battle], "cpu")
    tesla_card = int(runtime.battle.entity_card[0, _slot(runtime, 0, tesla.id)].item())
    ghost_card = int(runtime.battle.entity_card[1, _slot(runtime, 1, ghost.id)].item())
    assert owner.catalog.hide_supported_core[tesla_card].item()
    assert not owner.catalog.fade_supported_core[tesla_card].item()
    assert owner.catalog.fade_supported_core[ghost_card].item()
    assert not owner.catalog.hide_supported_core[ghost_card].item()
