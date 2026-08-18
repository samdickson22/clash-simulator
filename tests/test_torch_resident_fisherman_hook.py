from __future__ import annotations

import copy
from typing import Any, cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.kinematics import tiles_to_logic_units
from clasher.torch_sim.resident_fisherman_hook import (
    HookLifecycleEventOpcode,
    TensorResidentFishermanHooks,
)
from clasher.torch_sim.runtime_state import TensorBattleRuntime
from clasher.torch_sim.special_movement import HookPhase


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _spawn(
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


def _troop_battle() -> tuple[BattleState, Troop, Troop]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    fisherman = _spawn(battle, "Fisherman", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Knight", 1, Position(9.0, 16.0))
    fisherman.position = Position(9.0, 10.0)
    target.position = Position(9.0, 16.0)
    target.attack_cooldown = 0.2
    target.target_id = fisherman.id
    cast(Any, target)._last_combat_target_id = fisherman.id
    return battle, fisherman, target


def _building_battle() -> tuple[BattleState, Troop, Building]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    fisherman = _spawn(battle, "Fisherman", 0, Position(9.0, 10.0))
    stats = battle.card_loader.get_card("Cannon")
    assert stats is not None
    target = battle._spawn_entity(Building, Position(9.0, 16.0), 1, stats)
    assert isinstance(target, Building)
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target.on_spawn()
    return battle, fisherman, target


def _stack(
    battles: list[BattleState],
    device: str,
) -> tuple[TensorBattleRuntime, TensorResidentFishermanHooks]:
    runtime = TensorBattleRuntime.from_battles(
        [copy.deepcopy(battle) for battle in battles],
        device=device,
        max_entities=8,
        event_capacity=64,
    )
    return runtime, TensorResidentFishermanHooks.from_battles(runtime, battles)


def _slot(runtime: TensorBattleRuntime, row: int, entity_id: int) -> int:
    return runtime.battle.entity_id[row].tolist().index(entity_id)


def _mechanic(entity: Troop) -> Any:
    return next(
        mechanic
        for mechanic in entity.mechanics
        if type(mechanic).__name__ == "FishermanHook"
    )


def _phase(mechanic: Any) -> HookPhase:
    return HookPhase(
        {
            "idle": HookPhase.IDLE,
            "windup": HookPhase.WINDUP,
            "flight": HookPhase.FLIGHT,
            "drag": HookPhase.DRAG,
        }[mechanic.state]
    )


def _scalar_tick(source: Troop, mechanic: Any) -> None:
    mechanic.on_tick(source, 50)
    mechanic.on_object_tick(source, 50)


def _assert_trace(
    runtime: TensorBattleRuntime,
    owner: TensorResidentFishermanHooks,
    source: Troop,
    target: Troop | Building,
    mechanic: Any,
) -> None:
    source_slot = _slot(runtime, 0, source.id)
    target_slot = _slot(runtime, 0, target.id)
    assert owner.state.phase[0, source_slot].item() == int(_phase(mechanic))
    assert owner.state.windup_remaining_ms[0, source_slot].item() == pytest.approx(
        mechanic.windup_remaining_ms
    )
    assert runtime.battle.entity_x_units[0, source_slot].item() == (
        tiles_to_logic_units(source.position.x)
    )
    assert runtime.battle.entity_y_units[0, source_slot].item() == (
        tiles_to_logic_units(source.position.y)
    )
    assert runtime.battle.entity_x_units[0, target_slot].item() == (
        tiles_to_logic_units(target.position.x)
    )
    assert runtime.battle.entity_y_units[0, target_slot].item() == (
        tiles_to_logic_units(target.position.y)
    )
    assert owner.state.target_forced[0, source_slot].item() is bool(
        target.forced_movement_active
    )
    assert owner.state.special_active[0, source_slot].item() is bool(
        getattr(source, "_special_move_active", False)
    )
    if mechanic.hook_position is None:
        assert owner.state.hook_position_units[0, source_slot].tolist() == [0, 0]
    else:
        assert owner.state.hook_position_units[0, source_slot].tolist() == [
            tiles_to_logic_units(mechanic.hook_position.x),
            tiles_to_logic_units(mechanic.hook_position.y),
        ]


def test_full_windup_homing_flight_and_victim_drag_match_scalar(
    tensor_device: str,
) -> None:
    battle, fisherman, target = _troop_battle()
    runtime, owner = _stack([battle], tensor_device)
    mechanic = _mechanic(fisherman)
    source_slot = _slot(runtime, 0, fisherman.id)
    target_slot = _slot(runtime, 0, target.id)
    hp_before = target.hitpoints
    transition_opcodes: list[int] = []

    for _ in range(70):
        # Exercise flight homing with target motion before attachment.
        if mechanic.state == "flight" and mechanic.hook_position is not None:
            target.position.x += 0.1
            runtime.battle.entity_x_units[0, target_slot] = tiles_to_logic_units(
                target.position.x
            )
        _scalar_tick(fisherman, mechanic)
        result = owner.step_(runtime)

        assert result.committed.tolist() == [True]
        assert not result.damage.any()
        assert runtime.events.count.tolist() == [0]
        assert runtime.battle.rng.python_state(0) == battle.rng.getstate()
        _assert_trace(runtime, owner, fisherman, target, mechanic)
        transition_opcodes.extend(
            result.combat_events.opcode[0][result.combat_events.valid[0]].tolist()
        )
        transition_opcodes.extend(
            result.object_events.opcode[0][result.object_events.valid[0]].tolist()
        )
        if mechanic.state == "idle" and transition_opcodes:
            break

    assert transition_opcodes == [
        int(HookLifecycleEventOpcode.WINDUP_STARTED),
        int(HookLifecycleEventOpcode.PROJECTILE_LAUNCHED),
        int(HookLifecycleEventOpcode.TARGET_ATTACHED),
        int(HookLifecycleEventOpcode.FINISHED),
    ]
    assert target.hitpoints == hp_before
    assert target.attack_cooldown == pytest.approx(
        target.get_base_attack_interval_seconds()
    )
    assert owner.combat.attack_cooldown[0, target_slot].item() == (
        target.attack_cooldown
    )
    assert target.target_id == fisherman.id
    assert owner.combat_target_entity_id[0, target_slot].item() == fisherman.id
    assert not owner.combat.forced_movement[0, target_slot].item()
    assert owner.state.phase[0, source_slot].item() == int(HookPhase.IDLE)


def test_building_target_pulls_fisherman_without_moving_building(
    tensor_device: str,
) -> None:
    battle, fisherman, target = _building_battle()
    runtime, owner = _stack([battle], tensor_device)
    mechanic = _mechanic(fisherman)
    target_position = Position(target.position.x, target.position.y)

    for _ in range(80):
        _scalar_tick(fisherman, mechanic)
        result = owner.step_(runtime)
        assert result.committed.tolist() == [True]
        _assert_trace(runtime, owner, fisherman, target, mechanic)
        if mechanic.state == "idle" and fisherman.position.y > 10.0:
            break

    assert target.position == target_position
    assert fisherman.position.y > 10.0
    assert fisherman.position.distance_to(target.position) == pytest.approx(
        fisherman.get_collision_radius()
        + target.get_collision_radius()
        + mechanic.drag_margin
    )


def test_inflight_target_plane_loss_cancels_without_damage(
    tensor_device: str,
) -> None:
    battle, fisherman, target = _troop_battle()
    runtime, owner = _stack([battle], tensor_device)
    mechanic = _mechanic(fisherman)
    source_slot = _slot(runtime, 0, fisherman.id)
    target_slot = _slot(runtime, 0, target.id)
    while mechanic.state != "flight":
        _scalar_tick(fisherman, mechanic)
        assert owner.step_(runtime).committed.tolist() == [True]
    target_position = Position(target.position.x, target.position.y)
    cast(Any, target)._river_jump_active = True
    plane = torch.ones_like(runtime.entity_pool.active)
    plane[0, target_slot] = False

    _scalar_tick(fisherman, mechanic)
    cancelled = owner.step_(runtime, target_plane_valid=plane)

    assert mechanic.state == "idle"
    assert owner.state.phase[0, source_slot].item() == int(HookPhase.IDLE)
    assert cancelled.object_events.opcode[0, source_slot].item() == int(
        HookLifecycleEventOpcode.CANCELLED
    )
    assert target.position == target_position
    assert target.hitpoints == target.max_hitpoints
    assert owner.combat_target_entity_id[0, source_slot].item() == 0


def test_stun_cancels_windup_and_clears_source_lock(
    tensor_device: str,
) -> None:
    battle, fisherman, _target = _troop_battle()
    runtime, owner = _stack([battle], tensor_device)
    mechanic = _mechanic(fisherman)
    source_slot = _slot(runtime, 0, fisherman.id)
    _scalar_tick(fisherman, mechanic)
    assert owner.step_(runtime).committed.tolist() == [True]
    assert mechanic.state == "windup"
    fisherman.apply_stun(0.5, source_kind="Zap")
    runtime.status.stun_timer[0, source_slot] = 0.5

    _scalar_tick(fisherman, mechanic)
    result = owner.step_(runtime)

    assert result.committed.tolist() == [True]
    assert mechanic.state == "idle"
    assert owner.state.phase[0, source_slot].item() == int(HookPhase.IDLE)
    assert owner.combat_target_entity_id[0, source_slot].item() == 0
    assert owner.combat.target_slot[0, source_slot].item() == -1
    assert result.combat_events.opcode[0, source_slot].item() == int(
        HookLifecycleEventOpcode.CANCELLED
    )


def test_clone_fork_reset_and_mixed_identity_rollback_are_atomic() -> None:
    left, left_source, _ = _troop_battle()
    right, right_source, _ = _troop_battle()
    runtime, owner = _stack([left, right], "cpu")
    left_slot = _slot(runtime, 0, left_source.id)
    right_slot = _slot(runtime, 1, right_source.id)
    right_target_slot = 1 - right_slot
    before = owner.clone()
    before_positions = runtime.battle.entity_y_units.clone()
    swapped = runtime.battle.entity_id[
        1, torch.tensor([right_slot, right_target_slot])
    ].flip(0)
    runtime.battle.entity_id[1, right_slot] = swapped[0]
    runtime.battle.entity_id[1, right_target_slot] = swapped[1]

    result = owner.step_(runtime)

    assert result.committed.tolist() == [True, False]
    assert owner.state.phase[0, left_slot].item() == int(HookPhase.WINDUP)
    assert torch.equal(owner.state.phase[1], before.state.phase[1])
    assert torch.equal(runtime.battle.entity_y_units[1], before_positions[1])

    clone = owner.clone()
    clone.state.windup_remaining_ms[0, left_slot] = 17.0
    assert owner.state.windup_remaining_ms[0, left_slot].item() != 17.0
    fork = clone.fork([0])
    assert fork.state.windup_remaining_ms[0, left_slot].item() == 17.0
    clone.reset_rows_([0], owner, [0])
    assert clone.state.windup_remaining_ms[0, left_slot].item() == (
        owner.state.windup_remaining_ms[0, left_slot].item()
    )


def test_catalog_support_is_serialized_opcode_driven() -> None:
    battle, fisherman, _ = _troop_battle()
    runtime, owner = _stack([battle], "cpu")
    source_slot = _slot(runtime, 0, fisherman.id)
    card = int(runtime.battle.entity_card[0, source_slot].item())
    operation = owner.catalog.operation_slot[card]
    special_card = owner.catalog.core_to_special[card]
    assert owner.catalog.supported_core[card].item()
    assert owner.catalog.special.opcode[special_card, operation].item() == 4
    assert owner.catalog.special.windup_ms[special_card, operation].item() == 1_300
    assert owner.catalog.special.speed_units[special_card, operation].item() == 800
    assert (
        owner.catalog.special.secondary_speed_units[special_card, operation].item()
        == 850
    )
    assert (
        owner.catalog.special.tertiary_speed_units[special_card, operation].item()
        == 450
    )
    assert owner.catalog.special.margin_units[special_card, operation].item() == 200
