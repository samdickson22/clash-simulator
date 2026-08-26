from __future__ import annotations

from collections import deque
from typing import cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.mechanic_dispatcher import (
    MechanicTickInputs,
    TensorMechanicDispatcher,
)
from clasher.torch_sim.observations import TensorObservationProjector
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.runtime_state import TensorBattleRuntime
from clasher.torch_sim.special_movement import LeapPhase

DEPLOY_MEGA_KNIGHT = 14 * 18 + 9


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = cast(Troop, battle._spawn_entity(Troop, position, player, stats))
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _slot(runtime: TensorBattleRuntime, entity_id: int) -> int:
    slots = torch.nonzero(
        runtime.battle.entity_id[0] == entity_id,
        as_tuple=False,
    ).flatten()
    assert slots.numel() == 1
    return int(slots.item())


def _engine_slot(engine: TensorResidentEngine, entity_id: int) -> int:
    return _slot(engine.runtime, entity_id)


def test_mega_knight_is_a_serialized_special_movement_composition() -> None:
    battle = BattleState(fast_path=False)
    definition = battle.card_loader.load_card_definitions()["MegaKnight"]
    stats = battle.card_loader.get_card("MegaKnight")

    assert stats is not None
    assert tuple(type(item).__name__ for item in definition.mechanics) == (
        "MegaKnightSlam",
        "SpawnPushback",
    )
    character = stats._raw_entry["summonCharacterData"]
    deployment = stats._raw_entry["projectileData"]
    assert character["dashCooldown"] == 900
    assert character["dashConstantTime"] == 800
    assert character["dashLandingTime"] == 300
    assert character["dashMinRange"] == 3_500
    assert character["dashMaxRange"] == 5_000
    assert character["dashRadius"] == deployment["radius"] == 2_200
    assert character["dashPushBack"] == deployment["pushback"] == 1_000


def test_serialized_dispatcher_closes_policy_visible_spawn_and_leap_lifecycle() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    mega = _spawn(battle, "MegaKnight", 0, Position(9.0, 10.0))
    spawn_target = _spawn(battle, "Knight", 1, Position(10.0, 10.0))
    leap_target = _spawn(battle, "Knight", 1, Position(9.0, 15.0))
    mega.target_id = leap_target.id
    for target in (spawn_target, leap_target):
        target.stun_timer = 100.0
        target.attack_cooldown = 100.0

    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=16, event_capacity=512
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    mega_slot = _slot(runtime, mega.id)
    spawn_slot = _slot(runtime, spawn_target.id)
    leap_slot = _slot(runtime, leap_target.id)
    spawn_hp = float(runtime.battle.entity_hp[0, spawn_slot].item())
    leap_hp = float(runtime.battle.entity_hp[0, leap_slot].item())
    spawn_position = torch.tensor([10_000, 10_000], dtype=torch.int32)
    saw_airborne = False
    saw_landing = False

    for tick in range(48):
        inputs = MechanicTickInputs.empty(dispatcher)
        inputs.connected_target_slot[0, mega_slot] = leap_slot
        inputs.connected[0, mega_slot] = runtime.battle.entity_active[0, leap_slot]
        inputs.special_target_in_range[0, mega_slot] = True
        if tick == 0:
            inputs.spawned[0, mega_slot] = True

        result = dispatcher.step(inputs)
        assert result.committed.tolist() == [True]
        phase = int(dispatcher.leap.phase[0, mega_slot].item())
        saw_airborne |= phase == int(LeapPhase.AIRBORNE)
        saw_landing |= phase == int(LeapPhase.LANDING)
        if (
            saw_landing
            and phase == int(LeapPhase.IDLE)
            and runtime.battle.entity_hp[0, leap_slot].item() < leap_hp
        ):
            break
    else:
        pytest.fail("serialized Mega Knight leap did not finish")

    stats = battle.card_loader.get_card("MegaKnight")
    assert stats is not None
    assert saw_airborne and saw_landing
    assert runtime.battle.entity_hp[0, spawn_slot].item() == pytest.approx(
        spawn_hp - float(stats.get_scaled_stat(168))
    )
    assert runtime.battle.entity_hp[0, leap_slot].item() == pytest.approx(
        leap_hp - float(stats.get_scaled_stat(210))
    )
    assert not torch.equal(
        dispatcher.knockback_target_units[0, spawn_slot].to(torch.int32),
        spawn_position,
    )
    assert runtime.battle.entity_x_units[0, mega_slot].item() == 9_000
    expected_landing_y = round(
        (
            leap_target.position.y
            - stats.range
            - leap_target.get_collision_radius()
        )
        * 1_000
    )
    assert runtime.battle.entity_y_units[0, mega_slot].item() == expected_landing_y

    projector = TensorObservationProjector.from_battles(
        [battle],
        state=runtime.battle,
        structured_builder=StructuredObservationBuilder(max_entities=16),
        cv_builder=CvObservationBuilder(),
    )
    projected = projector.project_structured()
    actor_ids = projected.entity_ids[0, 0]
    actor_mask = projected.entity_mask[0, 0]
    leap_token = int(projector.entity_token[0, leap_slot].item())
    assert leap_token in actor_ids[actor_mask].tolist()
    knight_indices = torch.nonzero(
        actor_mask & (actor_ids == leap_token), as_tuple=False
    ).flatten()
    observed_fractions = sorted(
        projected.entity_features[0, 0, knight_indices, 9].tolist()
    )
    expected_fractions = sorted(
        float(runtime.battle.entity_hp[0, slot])
        / float(runtime.battle.entity_max_hp[0, slot])
        for slot in (spawn_slot, leap_slot)
    )
    assert observed_fractions == pytest.approx(expected_fractions, abs=1e-6)


def test_resident_action_waits_for_deploy_hook_before_spawn_slam() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    target = _spawn(battle, "Knight", 1, Position(10.5, 14.5))
    target.stun_timer = 100.0
    target.attack_cooldown = 100.0
    player = battle.players[0]
    player.hand = ["MegaKnight", "Knight", "Zap", "Cannon"]
    player.deck = [str(name) for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0

    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=24, max_objects=16, event_capacity=512
    )
    target_slot = _engine_slot(engine, target.id)
    initial_hp = float(engine.runtime.battle.entity_hp[0, target_slot].item())
    initial_position = torch.stack(
        (
            engine.runtime.battle.entity_x_units[0, target_slot],
            engine.runtime.battle.entity_y_units[0, target_slot],
        )
    ).clone()
    actions = torch.tensor([[DEPLOY_MEGA_KNIGHT, NO_OP_ACTION]])

    assert engine.preflight(actions).supported.tolist() == [True]
    first = engine.step(actions, player_order=torch.tensor([[0, 1]]))
    assert first.committed.tolist() == [True]
    allocation = first.deployment.deployment.allocation
    spawned_slot = int(allocation.slots[0][allocation.valid[0]][0].item())
    owner = engine.mechanic_deployment.catalog.owner_index("combat_dispatch")
    assert first.deployment.committed.tolist() == [True]
    assert engine.mechanic_deployment.state.owner_entity_id[
        owner, 0, spawned_slot
    ].item() == engine.runtime.battle.entity_id[0, spawned_slot].item()
    assert engine.runtime.battle.entity_hp[0, target_slot].item() == initial_hp

    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64)
    for _ in range(18):
        result = engine.step(noop, player_order=torch.tensor([[0, 1]]))
        assert result.committed.tolist() == [True]
        assert engine.runtime.battle.entity_hp[0, target_slot].item() == initial_hp

    landed = engine.step(noop, player_order=torch.tensor([[0, 1]]))
    assert landed.committed.tolist() == [True]
    stats = battle.card_loader.get_card("MegaKnight")
    assert stats is not None
    assert engine.runtime.battle.entity_hp[0, target_slot].item() == pytest.approx(
        initial_hp - float(stats.get_scaled_stat(168))
    )
    assert engine.projectile_bridge.knockback_active[0, target_slot].item()
    final_position = torch.stack(
        (
            engine.runtime.battle.entity_x_units[0, target_slot],
            engine.runtime.battle.entity_y_units[0, target_slot],
        )
    )
    assert not torch.equal(final_position, initial_position)


def test_resident_leap_consumes_only_mega_knight_movement_component() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    mega = _spawn(battle, "MegaKnight", 0, Position(9.0, 10.0))
    leap_target = _spawn(battle, "Knight", 1, Position(9.0, 15.0))
    ordinary_mover = _spawn(battle, "Knight", 0, Position(3.0, 10.0))
    distant_target = _spawn(battle, "Knight", 1, Position(3.0, 24.0))
    mega.target_id = leap_target.id
    mega._movement_target_id = leap_target.id
    ordinary_mover.target_id = distant_target.id
    ordinary_mover._movement_target_id = distant_target.id
    for target in (leap_target, distant_target):
        target.stun_timer = 100.0
        target.attack_cooldown = 100.0

    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=24, max_objects=16, event_capacity=512
    )
    mega_slot = _engine_slot(engine, mega.id)
    leap_slot = _engine_slot(engine, leap_target.id)
    mover_slot = _engine_slot(engine, ordinary_mover.id)
    mover_start = torch.stack(
        (
            engine.runtime.battle.entity_x_units[0, mover_slot],
            engine.runtime.battle.entity_y_units[0, mover_slot],
        )
    ).clone()
    leap_hp = float(engine.runtime.battle.entity_hp[0, leap_slot].item())
    saw_airborne = False
    saw_landing = False

    for _ in range(48):
        result = engine.step(player_order=torch.tensor([[0, 1]]))
        assert result.committed.tolist() == [True]
        phase = int(engine.dispatcher.leap.phase[0, mega_slot].item())
        saw_airborne |= phase == int(LeapPhase.AIRBORNE)
        saw_landing |= phase == int(LeapPhase.LANDING)
        if (
            saw_landing
            and phase == int(LeapPhase.IDLE)
            and engine.runtime.battle.entity_hp[0, leap_slot].item() < leap_hp
        ):
            break
    else:
        pytest.fail("resident Mega Knight leap did not finish")

    mover_end = torch.stack(
        (
            engine.runtime.battle.entity_x_units[0, mover_slot],
            engine.runtime.battle.entity_y_units[0, mover_slot],
        )
    )
    assert saw_airborne and saw_landing
    assert not torch.equal(mover_end, mover_start)
    assert engine.runtime.battle.entity_y_units[0, mega_slot].item() == 13_300
    assert engine.runtime.battle.entity_hp[0, leap_slot].item() < leap_hp
    assert engine.projectile_bridge.knockback_active[0, leap_slot].item()
