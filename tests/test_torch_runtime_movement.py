from __future__ import annotations

from dataclasses import fields

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
from clasher.torch_sim.movement_adapter import TensorMovementAdapter
from clasher.torch_sim.runtime import TensorTickRuntime
from clasher.torch_sim.runtime_movement import (
    MovementEventOpcode,
    step_runtime_movement_,
)

DEVICES = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])


def _empty_battle() -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    return battle


def _troop(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    entity = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity.on_spawn()
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _building(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Building:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_entity(Building, position, player_id, stats)
    entity = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Building)
    )
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _movement_phase_oracle(battle: BattleState) -> None:
    for entity in sorted(battle.entities.values(), key=lambda item: item.id):
        if not isinstance(entity, (Troop, Building)) or not entity.is_alive:
            continue
        if isinstance(entity, Troop):
            battle._accumulate_troop_collision_for(entity)
        entity.begin_movement_tick()
        try:
            entity.update_movement_component(battle.dt, battle)
        finally:
            entity.finish_movement_tick(battle)
            entity.quantize_logic_position()


def _movement_state(entity: Entity) -> tuple[object, ...]:
    return (
        entity.position.x,
        entity.position.y,
        entity._facing_x_units,
        entity._facing_y_units,
        entity._movement_vector_x_units,
        entity._movement_vector_y_units,
        entity._movement_vector_count,
        entity._movement_vector_bypasses_cap,
        entity._pending_movement_x,
        entity._pending_movement_y,
        entity._pending_movement_consumed,
        getattr(entity, "_native_avoidance", 0),
        getattr(entity, "_native_natural_movement_active", False),
        tuple(getattr(entity, "_native_ground_route_cells", [])),
        getattr(entity, "_ground_path_cache_key", None),
        getattr(entity, "_ground_path_cache_backwards", False),
        entity._ground_path_backwards,
        getattr(entity, "_river_jump_active", False),
        getattr(entity, "_river_jump_blocked", False),
        getattr(entity, "_river_jump_elapsed", 0.0),
        getattr(entity, "_river_jump_duration", 0.0),
        getattr(entity, "_special_move_active", False),
        getattr(entity, "_special_move_consumed_tick", False),
    )


def _runtime_and_adapter(
    battle: BattleState,
    *,
    device: str,
    capacity: int = 16,
) -> tuple[TensorTickRuntime, TensorMovementAdapter]:
    runtime = TensorTickRuntime.from_battles(
        [battle], max_entities=capacity, device=device
    )
    adapter = TensorMovementAdapter.from_battles(
        [battle], max_entities=capacity, device=device
    )
    return runtime, adapter


@pytest.mark.parametrize("device", DEVICES)
def test_runtime_ordinary_route_movement_matches_complete_scalar_phase(
    device: str,
) -> None:
    seed = _empty_battle()
    mover = _troop(seed, "Knight", 0, Position(4.25, 10.25))
    target = _troop(seed, "Knight", 1, Position(5.25, 13.75))
    mover._movement_target_id = target.id
    expected = seed.clone()
    candidate = seed.clone()
    _movement_phase_oracle(expected)
    runtime, adapter = _runtime_and_adapter(candidate, device=device)

    result = step_runtime_movement_(runtime, adapter)
    adapter.sync_to_battles([candidate])

    assert result.supported_batch.tolist() == [True]
    assert result.ordinary_moved.any().item()
    assert result.route_advanced.any().item()
    assert MovementEventOpcode.ROUTE_NODE_ADVANCED in result.events.opcode[0].tolist()
    for entity_id in sorted(expected.entities):
        assert _movement_state(candidate.entities[entity_id]) == _movement_state(
            expected.entities[entity_id]
        )
    mover_slot = adapter.slots_for_ids(0, [mover.id])[0]
    assert int(runtime.combat.x_units[0, mover_slot].item()) == round(
        expected.entities[mover.id].position.x * 1_000
    )
    assert int(runtime.combat.y_units[0, mover_slot].item()) == round(
        expected.entities[mover.id].position.y * 1_000
    )


@pytest.mark.parametrize("device", DEVICES)
def test_runtime_sequential_crowded_collision_matches_id_ordered_oracle(
    device: str,
) -> None:
    seed = _empty_battle()
    ground_a = _troop(seed, "Knight", 0, Position(9.0, 10.0))
    ground_b = _troop(seed, "Giant", 1, Position(9.5, 10.0))
    ground_c = _troop(seed, "Musketeer", 0, Position(10.0, 10.0))
    air = _troop(seed, "MegaMinion", 1, Position(9.25, 10.0))
    _building(seed, "Cannon", 1, Position(8.55, 10.0))
    expected = seed.clone()
    candidate = seed.clone()
    _movement_phase_oracle(expected)
    runtime, adapter = _runtime_and_adapter(candidate, device=device)

    result = step_runtime_movement_(runtime, adapter)
    adapter.sync_to_battles([candidate])

    assert result.supported_batch.tolist() == [True]
    assert int(result.collision.contact_count.sum().item()) >= 5
    assert int(result.collision_only_moved[0, :3].sum().item()) >= 2
    assert not result.collision_only_moved[
        0, adapter.slots_for_ids(0, [air.id])[0]
    ].item()
    for entity_id in sorted(expected.entities):
        assert _movement_state(candidate.entities[entity_id]) == _movement_state(
            expected.entities[entity_id]
        )
    assert ground_a.id < ground_b.id < ground_c.id < air.id


@pytest.mark.parametrize("finish", [False, True])
@pytest.mark.parametrize("device", DEVICES)
def test_runtime_active_river_jump_matches_scalar_and_emits_finish(
    device: str,
    finish: bool,
) -> None:
    seed = _empty_battle()
    hog = _troop(seed, "HogRider", 0, Position(9.25, 14.75))
    landing = Position(9.25, 14.85 if finish else 17.25)
    hog._river_jump_origin = Position(hog.position.x, hog.position.y)
    hog._river_jump_target = landing
    hog._river_jump_elapsed = 0.1
    hog._river_jump_duration = 0.75
    hog._river_jump_active = True
    hog._river_jump_blocked = False
    hog._special_move_active = True
    hog._special_move_consumed_tick = False
    expected = seed.clone()
    candidate = seed.clone()
    _movement_phase_oracle(expected)
    runtime, adapter = _runtime_and_adapter(candidate, device=device)

    result = step_runtime_movement_(runtime, adapter)
    adapter.sync_to_battles([candidate])

    assert result.supported_batch.tolist() == [True]
    slot = adapter.slots_for_ids(0, [hog.id])[0]
    assert result.river_jump_moved[0, slot].item()
    assert result.river_jump_finished[0, slot].item() is finish
    assert (
        MovementEventOpcode.RIVER_JUMP_FINISHED in result.events.opcode[0].tolist()
    ) is finish
    assert _movement_state(candidate.entities[hog.id]) == _movement_state(
        expected.entities[hog.id]
    )


def test_runtime_ordinary_avoidance_prepass_matches_scalar_component() -> None:
    battle = _empty_battle()
    mover = _troop(battle, "Knight", 0, Position(9.0, 10.0))
    target = _troop(battle, "Knight", 1, Position(9.5, 10.0))
    mover._movement_target_id = target.id
    mover._facing_x_units, mover._facing_y_units = (256, 0)
    expected = battle.clone()
    _movement_phase_oracle(expected)
    runtime, adapter = _runtime_and_adapter(battle, device="cpu")

    result = step_runtime_movement_(runtime, adapter)
    adapter.sync_to_battles([battle])

    assert result.supported_batch.tolist() == [True]
    assert result.unsupported_reasons == (None,)
    for entity_id in sorted(expected.entities):
        assert _movement_state(battle.entities[entity_id]) == _movement_state(
            expected.entities[entity_id]
        )


def test_finished_early_river_lane_rejoins_ground_collision_for_later_ids() -> None:
    seed = _empty_battle()
    hog = _troop(seed, "HogRider", 0, Position(9.25, 14.75))
    later_ground = _troop(seed, "Knight", 1, Position(9.25, 15.85))
    # Directly displaced characters may occupy an unwalkable river point; the
    # spawn primitive itself correctly snaps ordinary deployments to land.
    later_ground.position = Position(9.25, 15.85)
    hog._river_jump_origin = Position(hog.position.x, hog.position.y)
    hog._river_jump_target = Position(9.25, 14.91)
    hog._river_jump_elapsed = 0.0
    hog._river_jump_duration = 0.05
    hog._river_jump_active = True
    hog._river_jump_blocked = False
    hog._special_move_active = True
    expected = seed.clone()
    candidate = seed.clone()
    _movement_phase_oracle(expected)
    runtime, adapter = _runtime_and_adapter(candidate, device="cpu")

    result = step_runtime_movement_(runtime, adapter)
    adapter.sync_to_battles([candidate])

    assert result.supported_batch.tolist() == [True]
    hog_slot, later_slot = adapter.slots_for_ids(0, [hog.id, later_ground.id])
    assert result.river_jump_finished[0, hog_slot].item()
    assert int(result.collision.contact_count[0, later_slot].item()) == 1
    assert result.collision_only_moved[0, later_slot].item()
    assert _movement_state(candidate.entities[hog.id]) == _movement_state(
        expected.entities[hog.id]
    )
    assert _movement_state(candidate.entities[later_ground.id]) == _movement_state(
        expected.entities[later_ground.id]
    )


def test_runtime_mixed_batch_preserves_every_unsupported_row_tensor() -> None:
    supported_battle = _empty_battle()
    mover = _troop(supported_battle, "Knight", 0, Position(4.0, 10.0))
    target = _troop(supported_battle, "Knight", 1, Position(4.0, 13.0))
    mover._movement_target_id = target.id

    unsupported_battle = _empty_battle()
    prince = _troop(unsupported_battle, "Prince", 0, Position(14.0, 10.0))
    prince_target = _troop(unsupported_battle, "Knight", 1, Position(14.0, 13.0))
    prince._movement_target_id = prince_target.id

    battles = [supported_battle, unsupported_battle]
    runtime = TensorTickRuntime.from_battles(battles, max_entities=8)
    adapter = TensorMovementAdapter.from_battles(battles, max_entities=8)
    runtime_before = {
        (type(owner).__name__, descriptor.name): getattr(owner, descriptor.name)[
            1
        ].clone()
        for owner in (runtime.core, runtime.combat)
        for descriptor in fields(owner)
        if isinstance(getattr(owner, descriptor.name), torch.Tensor)
        and getattr(owner, descriptor.name).ndim > 0
        and getattr(owner, descriptor.name).shape[0] == 2
    }
    adapter_before = {
        descriptor.name: getattr(adapter, descriptor.name)[1].clone()
        for descriptor in fields(adapter)
        if isinstance(getattr(adapter, descriptor.name), torch.Tensor)
        and getattr(adapter, descriptor.name).ndim > 0
        and getattr(adapter, descriptor.name).shape[0] == 2
    }

    result = step_runtime_movement_(runtime, adapter)

    assert result.supported_batch.tolist() == [True, False]
    assert result.unsupported_reasons[1] == (
        "ordinary movement support mask rejected an active mover"
    )
    for owner in (runtime.core, runtime.combat):
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            key = (type(owner).__name__, descriptor.name)
            if key in runtime_before:
                assert torch.equal(value[1], runtime_before[key]), key
    for descriptor in fields(adapter):
        value = getattr(adapter, descriptor.name)
        if descriptor.name in adapter_before:
            assert torch.equal(value[1], adapter_before[descriptor.name]), (
                descriptor.name
            )


def test_runtime_fails_closed_when_lower_id_target_moves_before_route_use() -> None:
    battle = _empty_battle()
    earlier_target = _troop(battle, "Knight", 1, Position(5.0, 13.0))
    later_mover = _troop(battle, "Knight", 0, Position(5.0, 10.0))
    target_for_earlier = _troop(battle, "Knight", 0, Position(7.0, 16.0))
    earlier_target._movement_target_id = target_for_earlier.id
    later_mover._movement_target_id = earlier_target.id
    runtime, adapter = _runtime_and_adapter(battle, device="cpu")

    result = step_runtime_movement_(runtime, adapter)

    assert result.supported_batch.tolist() == [False]
    assert result.unsupported_reasons == (
        "earlier target movement requires native route refresh",
    )


def test_runtime_rejects_adapter_identity_mismatch_without_mutation() -> None:
    battle = _empty_battle()
    _troop(battle, "Knight", 0, Position(4.0, 10.0))
    runtime, adapter = _runtime_and_adapter(battle, device="cpu")
    adapter.entity_id[0, 0] += 100
    before = runtime.combat.x_units.clone()

    result = step_runtime_movement_(runtime, adapter)

    assert result.supported_batch.tolist() == [False]
    assert result.unsupported_reasons == (
        "movement adapter entity identity/order mismatch",
    )
    assert torch.equal(runtime.combat.x_units, before)
