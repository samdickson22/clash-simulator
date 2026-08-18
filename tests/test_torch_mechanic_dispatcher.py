from __future__ import annotations

import copy
from types import MethodType
from typing import Any

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
from clasher.kinematics import tiles_to_logic_units
from clasher.mechanics.shared.spawner import PeriodicSpawner
from clasher.torch_sim.catalog import MECHANIC_OPCODE
from clasher.torch_sim.mechanic_dispatcher import (
    DispatchReason,
    MechanicTickInputs,
    TensorMechanicDispatcher,
)
from clasher.torch_sim.passive_mechanics import PassiveEventOpcode
from clasher.torch_sim.runtime_state import TensorBattleRuntime, TickPhase


def _battle() -> BattleState:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    battle._champion_ability_owner_ids.clear()
    return battle


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Entity:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    cls = Building if str(stats.card_type).casefold() == "building" else Troop
    entity = battle._spawn_entity(cls, position, player, stats)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _slot(runtime: TensorBattleRuntime, entity_id: int, row: int = 0) -> int:
    result = torch.nonzero(
        runtime.battle.entity_id[row] == entity_id, as_tuple=False
    ).flatten()
    assert result.numel() == 1
    return int(result.item())


def _mechanic(entity: Entity, name: str) -> Any:
    return next(item for item in entity.mechanics if type(item).__name__ == name)


def test_preflight_and_commit_are_independent_per_row() -> None:
    supported_battle = _battle()
    witch = _spawn(supported_battle, "Witch", 0, Position(9.0, 12.0))
    unsupported_battle = _battle()
    _spawn(unsupported_battle, "Bandit", 0, Position(9.0, 12.0))
    runtime = TensorBattleRuntime.from_battles(
        [supported_battle, unsupported_battle],
        max_entities=8,
        event_capacity=32,
    )
    dispatcher = TensorMechanicDispatcher.from_battles(
        runtime, [supported_battle, unsupported_battle]
    )
    before_unsupported = dispatcher.passive.periodic_time_since_spawn_ms[1].clone()
    rng_words = runtime.battle.rng.words.clone()
    inputs = MechanicTickInputs.empty(dispatcher, dt_ms=1_000)

    result = dispatcher.step(inputs)

    assert result.committed.tolist() == [True, False]
    assert result.preflight.reason.tolist() == [
        DispatchReason.NONE,
        DispatchReason.UNSUPPORTED_OPCODE,
    ]
    assert (
        result.preflight.unsupported_opcode[1].item() == MECHANIC_OPCODE["BanditDash"]
    )
    witch_slot = _slot(runtime, witch.id, 0)
    assert dispatcher.passive.periodic_pending_units[0, witch_slot].item() > 0
    assert runtime.events.count[0].item() > 0
    assert torch.equal(
        dispatcher.passive.periodic_time_since_spawn_ms[1], before_unsupported
    )
    assert torch.equal(runtime.battle.rng.words, rng_words)


def test_event_overflow_fails_closed_without_partial_shield_or_status_state() -> None:
    battle = _battle()
    source = _spawn(battle, "MiniSparkys", 0, Position(8.0, 12.0))
    target = _spawn(battle, "DarkPrince", 1, Position(9.0, 12.0))
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=1
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    source_slot = _slot(runtime, source.id)
    target_slot = _slot(runtime, target.id)
    inputs = MechanicTickInputs.empty(dispatcher)
    inputs.attack_source_slot[0, 0] = source_slot
    inputs.attack_target_slot[0, 0] = target_slot
    inputs.attack_damage[0, 0] = 10.0
    inputs.attack_valid[0, 0] = True
    inputs.status_eligible[0, 0] = True
    before = (
        runtime.battle.entity_hp.clone(),
        dispatcher.mechanics.shield_current.clone(),
        runtime.status.stun_timer.clone(),
        runtime.events.count.clone(),
        runtime.battle.rng.words.clone(),
    )

    result = dispatcher.step(inputs)

    assert result.committed.tolist() == [False]
    assert result.preflight.reason.tolist() == [DispatchReason.EVENT_CAPACITY]
    assert torch.equal(runtime.battle.entity_hp, before[0])
    assert torch.equal(dispatcher.mechanics.shield_current, before[1])
    assert torch.equal(runtime.status.stun_timer, before[2])
    assert torch.equal(runtime.events.count, before[3])
    assert torch.equal(runtime.battle.rng.words, before[4])


def test_exceptional_overflow_retry_commits_other_supported_rows() -> None:
    battles: list[BattleState] = []
    source_ids: list[int] = []
    target_ids: list[int] = []
    for _ in range(2):
        battle = _battle()
        source_ids.append(_spawn(battle, "MiniSparkys", 0, Position(8.0, 12.0)).id)
        target_ids.append(_spawn(battle, "DarkPrince", 1, Position(9.0, 12.0)).id)
        battles.append(battle)
    runtime = TensorBattleRuntime.from_battles(
        battles, max_entities=8, event_capacity=2
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, battles)
    runtime.events.append(
        phase=TickPhase.COMMANDS,
        opcode=1,
        valid=torch.tensor([[True], [False]]),
    )
    inputs = MechanicTickInputs.empty(dispatcher)
    for row in range(2):
        inputs.attack_source_slot[row, 0] = _slot(runtime, source_ids[row], row)
        inputs.attack_target_slot[row, 0] = _slot(runtime, target_ids[row], row)
        inputs.attack_damage[row, 0] = 10.0
        inputs.attack_valid[row, 0] = True
        inputs.status_eligible[row, 0] = True
    shield_before = dispatcher.mechanics.shield_current.clone()

    result = dispatcher.step(inputs)

    assert result.committed.tolist() == [False, True]
    assert result.preflight.reason.tolist() == [
        DispatchReason.EVENT_CAPACITY,
        DispatchReason.NONE,
    ]
    target_slot_0 = _slot(runtime, target_ids[0], 0)
    target_slot_1 = _slot(runtime, target_ids[1], 1)
    assert (
        dispatcher.mechanics.shield_current[0, target_slot_0]
        == (shield_before[0, target_slot_0])
    )
    assert (
        dispatcher.mechanics.shield_current[1, target_slot_1]
        < (shield_before[1, target_slot_1])
    )


def test_invalid_special_trigger_fails_preflight_without_state_mutation() -> None:
    battle = _battle()
    source = _spawn(battle, "Witch", 0, Position(8.0, 12.0))
    target = _spawn(battle, "Knight", 1, Position(9.0, 12.0))
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=16)
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    state_before = dispatcher.passive.periodic_time_since_spawn_ms.clone()
    rng_before = runtime.battle.rng.words.clone()
    inputs = MechanicTickInputs.empty(dispatcher)
    inputs.special_source_slot[0, 0] = _slot(runtime, source.id)
    inputs.special_target_slot[0, 0] = _slot(runtime, target.id)
    inputs.special_valid[0, 0] = True

    result = dispatcher.step(inputs)

    assert result.committed.tolist() == [False]
    assert result.preflight.reason.tolist() == [DispatchReason.INVALID_INPUT]
    assert torch.equal(dispatcher.passive.periodic_time_since_spawn_ms, state_before)
    assert torch.equal(runtime.battle.rng.words, rng_before)
    assert runtime.events.count.tolist() == [0]


def test_heterogeneous_row_dt_is_vectorized_for_ramp_and_spawner_clocks() -> None:
    battles: list[BattleState] = []
    ramp_ids: list[int] = []
    target_ids: list[int] = []
    witch_ids: list[int] = []
    for _ in range(2):
        battle = _battle()
        ramp_entity = _spawn(battle, "InfernoDragon", 0, Position(9.0, 12.0))
        target = _spawn(battle, "Knight", 1, Position(9.0, 13.0))
        witch = _spawn(battle, "Witch", 0, Position(12.0, 12.0))
        ramp_entity.target_id = target.id
        ramp_ids.append(ramp_entity.id)
        target_ids.append(target.id)
        witch_ids.append(witch.id)
        battles.append(battle)
    runtime = TensorBattleRuntime.from_battles(
        battles, max_entities=8, event_capacity=32
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, battles)
    inputs = MechanicTickInputs.empty(dispatcher)
    inputs.dt_ms[:] = torch.tensor([50, 100])
    for row in range(2):
        ramp_slot = _slot(runtime, ramp_ids[row], row)
        inputs.connected[row, ramp_slot] = True
        inputs.connected_target_slot[row, ramp_slot] = _slot(
            runtime, target_ids[row], row
        )

    result = dispatcher.step(inputs)

    assert result.committed.tolist() == [True, True]
    assert (
        dispatcher.damage_ramp.target_time_ms[0, _slot(runtime, ramp_ids[0], 0)].item()
        == 50
    )
    assert (
        dispatcher.damage_ramp.target_time_ms[1, _slot(runtime, ramp_ids[1], 1)].item()
        == 100
    )
    assert (
        dispatcher.passive.periodic_time_since_spawn_ms[
            0, _slot(runtime, witch_ids[0], 0)
        ].item()
        == 50
    )
    assert (
        dispatcher.passive.periodic_time_since_spawn_ms[
            1, _slot(runtime, witch_ids[1], 1)
        ].item()
        == 100
    )


def test_upstream_applied_damage_dispatches_status_without_double_hp_or_shield() -> (
    None
):
    battle = _battle()
    source = _spawn(battle, "MiniSparkys", 0, Position(8.0, 12.0))
    target = _spawn(battle, "DarkPrince", 1, Position(9.0, 12.0))
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=8
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    source_slot = _slot(runtime, source.id)
    target_slot = _slot(runtime, target.id)
    runtime.battle.entity_hp[0, target_slot] -= 7.0
    hp_before = runtime.battle.entity_hp.clone()
    shield_before = dispatcher.mechanics.shield_current.clone()
    inputs = MechanicTickInputs.empty(dispatcher)
    inputs.attack_source_slot[0, 0] = source_slot
    inputs.attack_target_slot[0, 0] = target_slot
    inputs.attack_damage[0, 0] = 7.0
    inputs.attack_valid[0, 0] = True
    inputs.attack_damage_already_applied[0, 0] = True
    inputs.status_eligible[0, 0] = True

    result = dispatcher.step(inputs)

    assert result.committed.item()
    assert torch.equal(runtime.battle.entity_hp, hp_before)
    assert torch.equal(dispatcher.mechanics.shield_current, shield_before)
    assert runtime.status.stun_timer[0, target_slot].item() > 0.0


def test_permuted_slots_and_reversed_hit_lanes_emit_stable_source_id_order() -> None:
    battle = _battle()
    source_a = _spawn(battle, "MiniSparkys", 0, Position(7.0, 12.0))
    target_a = _spawn(battle, "DarkPrince", 1, Position(8.0, 12.0))
    source_b = _spawn(battle, "MiniSparkys", 0, Position(10.0, 12.0))
    target_b = _spawn(battle, "DarkPrince", 1, Position(11.0, 12.0))
    battle.entities = {
        entity.id: entity for entity in (target_b, source_b, target_a, source_a)
    }
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=16
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    inputs = MechanicTickInputs.empty(dispatcher, event_width=2)
    for lane, (source, target) in enumerate(
        ((source_b, target_b), (source_a, target_a))
    ):
        inputs.attack_source_slot[0, lane] = _slot(runtime, source.id)
        inputs.attack_target_slot[0, lane] = _slot(runtime, target.id)
        inputs.attack_damage[0, lane] = 10.0
        inputs.attack_valid[0, lane] = True
        inputs.status_eligible[0, lane] = True

    result = dispatcher.step(inputs)

    assert result.committed.item()
    count = int(runtime.events.count[0].item())
    combat = runtime.events.phase[0, :count] == int(TickPhase.COMBAT)
    assert runtime.events.source_id[0, :count][combat].tolist() == [
        source_a.id,
        source_a.id,
        source_b.id,
        source_b.id,
    ]


def test_multi_family_tick_matches_python_oracles_and_stable_event_order() -> None:
    battle = _battle()
    on_hit = _spawn(battle, "MiniSparkys", 0, Position(8.0, 12.0))
    shield = _spawn(battle, "DarkPrince", 1, Position(9.0, 12.0))
    recoil = _spawn(battle, "Firecracker", 0, Position(5.0, 10.0))
    recoil_target = _spawn(battle, "Knight", 1, Position(6.0, 10.0))
    ramp = _spawn(battle, "InfernoDragon", 0, Position(10.0, 10.0))
    ramp_target = _spawn(battle, "Knight", 1, Position(10.0, 11.0))
    spawner = _spawn(battle, "Witch", 0, Position(15.0, 5.0))
    hidden = _spawn(battle, "Tesla", 0, Position(2.0, 2.0))
    fading = _spawn(battle, "RoyalGhost", 0, Position(4.0, 20.0))
    collector = _spawn(battle, "SkeletonKing", 0, Position(9.0, 20.0))
    dead = _spawn(battle, "Knight", 1, Position(10.0, 20.0))
    dead.is_alive = False
    ramp.target_id = ramp_target.id
    oracle = copy.deepcopy(battle)
    oracle_on_hit = oracle.entities[on_hit.id]
    oracle_shield = oracle.entities[shield.id]
    oracle_recoil = oracle.entities[recoil.id]
    oracle_recoil_target = oracle.entities[recoil_target.id]
    oracle_ramp = oracle.entities[ramp.id]
    oracle_ramp_target = oracle.entities[ramp_target.id]
    oracle_spawner = oracle.entities[spawner.id]
    oracle_hidden = oracle.entities[hidden.id]
    oracle_fading = oracle.entities[fading.id]
    oracle_collector = oracle.entities[collector.id]
    spawner_mechanic = _mechanic(oracle_spawner, "PeriodicSpawner")
    spawned: list[tuple[int, int]] = []

    def record_spawn(
        _self: PeriodicSpawner,
        _entity: Any,
        *,
        count: int,
        start_index: int,
        wave_size: int,
    ) -> None:
        spawned.extend(
            (index, wave_size) for index in range(start_index, start_index + count)
        )

    spawner_mechanic._spawn_units = MethodType(record_spawn, spawner_mechanic)

    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=32, event_capacity=256
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    rng_before = runtime.battle.rng.words.clone()

    for tick in range(20):
        _mechanic(oracle_collector, "SkeletonKingSoulCollector").on_tick(
            oracle_collector, 50
        )
        _mechanic(oracle_ramp, "DamageRamp").on_target_observed(
            oracle_ramp, oracle_ramp_target, 50
        )
        if tick == 0:
            oracle_shield.take_damage(10.0)
            _mechanic(oracle_on_hit, "SerializedOnHitBuff").on_attack_hit(
                oracle_on_hit, oracle_shield
            )
            _mechanic(oracle_recoil, "AttackRecoil").on_attack_committed(
                oracle_recoil, oracle_recoil_target
            )
            _mechanic(oracle_fading, "InvisibilityWhenNotAttacking").on_attack_start(
                oracle_fading, oracle_shield
            )
        _mechanic(oracle_hidden, "HideWhenIdle").on_object_tick(oracle_hidden, 50)
        _mechanic(oracle_fading, "InvisibilityWhenNotAttacking").on_object_tick(
            oracle_fading, 50
        )
        spawner_mechanic.on_object_tick(oracle_spawner, 50)

        inputs = MechanicTickInputs.empty(dispatcher)
        ramp_slot = _slot(runtime, ramp.id)
        inputs.connected_target_slot[0, ramp_slot] = _slot(runtime, ramp_target.id)
        inputs.connected[0, ramp_slot] = True
        if tick == 0:
            inputs.attack_source_slot[0, 0] = _slot(runtime, on_hit.id)
            inputs.attack_target_slot[0, 0] = _slot(runtime, shield.id)
            inputs.attack_damage[0, 0] = 10.0
            inputs.attack_valid[0, 0] = True
            inputs.status_eligible[0, 0] = True
            inputs.special_source_slot[0, 0] = _slot(runtime, recoil.id)
            inputs.special_target_slot[0, 0] = _slot(runtime, recoil_target.id)
            inputs.special_valid[0, 0] = True
            inputs.attack_committed[0, 0] = True
            inputs.attack_started[0, _slot(runtime, fading.id)] = True
        result = dispatcher.step(inputs)
        assert result.committed.tolist() == [True]

    shield_slot = _slot(runtime, shield.id)
    recoil_slot = _slot(runtime, recoil.id)
    collector_slot = _slot(runtime, collector.id)
    hidden_slot = _slot(runtime, hidden.id)
    fading_slot = _slot(runtime, fading.id)
    ramp_slot = _slot(runtime, ramp.id)
    spawner_slot = _slot(runtime, spawner.id)
    assert (
        dispatcher.mechanics.shield_current[0, shield_slot].item()
        == _mechanic(oracle_shield, "Shield").current_shield
    )
    assert runtime.status.stun_timer[0, shield_slot].item() == (
        oracle_shield.stun_timer
    )
    oracle_knockback = oracle_recoil._knockback_target
    assert oracle_knockback is not None
    assert dispatcher.knockback_target_units[0, recoil_slot].tolist() == [
        tiles_to_logic_units(oracle_knockback.x),
        tiles_to_logic_units(oracle_knockback.y),
    ]
    assert (
        dispatcher.damage_ramp.target_time_ms[0, ramp_slot].item()
        == _mechanic(oracle_ramp, "DamageRamp")._current_target_ms
    )
    assert dispatcher.damage_ramp.damage[0, ramp_slot].item() == oracle_ramp.damage
    assert (
        dispatcher.passive.souls_collected[0, collector_slot].item()
        == _mechanic(oracle_collector, "SkeletonKingSoulCollector").souls_collected
    )
    assert dispatcher.passive.hidden_building[0, hidden_slot].item() is bool(
        getattr(oracle_hidden, "_hidden_building")  # noqa: B009
    )
    assert (
        dispatcher.passive.fade_elapsed_ms[0, fading_slot].item()
        == _mechanic(oracle_fading, "InvisibilityWhenNotAttacking").time_since_attack_ms
    )
    assert dispatcher.passive.periodic_spawns_created[0, spawner_slot].item() == (
        spawner_mechanic.spawns_created
    )
    assert spawned
    assert torch.equal(runtime.battle.rng.words, rng_before)

    count = int(runtime.events.count[0].item())
    combat = runtime.events.phase[0, :count] == int(TickPhase.COMBAT)
    combat_sources = runtime.events.source_id[0, :count][combat].tolist()
    assert combat_sources == sorted(combat_sources)
    object_payloads = runtime.events.payload[0, :count][
        runtime.events.phase[0, :count] == int(TickPhase.OBJECTS)
    ].tolist()
    assert int(PassiveEventOpcode.PERIODIC_SPAWN) in object_payloads


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_transactional_dispatch_smoke() -> None:
    battle = _battle()
    _spawn(battle, "Witch", 0, Position(9.0, 12.0))
    runtime = TensorBattleRuntime.from_battles(
        [battle], device="cuda", max_entities=8, event_capacity=32
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])

    result = dispatcher.step(MechanicTickInputs.empty(dispatcher, dt_ms=1_000))

    assert result.committed.item()
    assert runtime.events.count.device.type == "cuda"
