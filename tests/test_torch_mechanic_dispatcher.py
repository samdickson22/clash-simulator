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
    *,
    deployed: bool = True,
) -> Entity:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    cls = Building if str(stats.card_type).casefold() == "building" else Troop
    entity = battle._spawn_entity(cls, position, player, stats)
    if deployed:
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
    _spawn(unsupported_battle, "ElectroDragon", 0, Position(9.0, 12.0))
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
        DispatchReason.CHILD_MATERIALIZATION,
    ]
    assert (
        result.preflight.unsupported_opcode[1].item()
        == MECHANIC_OPCODE["ElectroDragonChainLightning"]
    )
    witch_slot = _slot(runtime, witch.id, 0)
    assert dispatcher.passive.periodic_pending_units[0, witch_slot].item() > 0
    assert runtime.events.count[0].item() > 0
    assert torch.equal(
        dispatcher.passive.periodic_time_since_spawn_ms[1], before_unsupported
    )
    assert torch.equal(runtime.battle.rng.words, rng_words)


@pytest.mark.parametrize(
    ("card_name", "reason"),
    [
        ("ElectroDragon", DispatchReason.CHILD_MATERIALIZATION),
        ("ElectroSpirit", DispatchReason.CHILD_MATERIALIZATION),
        ("IceSpirit", DispatchReason.UNSUPPORTED_OPCODE),
        ("IceGolem", DispatchReason.CHILD_MATERIALIZATION),
        ("IceWizard", DispatchReason.CHILD_MATERIALIZATION),
        ("RageBarbarian", DispatchReason.CHILD_MATERIALIZATION),
        ("ElectroWizard", DispatchReason.CHILD_MATERIALIZATION),
    ],
)
def test_child_object_families_fail_closed_before_tensor_mutation(
    card_name: str, reason: DispatchReason
) -> None:
    battle = _battle()
    _spawn(battle, card_name, 0, Position(9.0, 12.0))
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=16)
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    hp_before = runtime.battle.entity_hp.clone()
    rng_before = runtime.battle.rng.words.clone()

    result = dispatcher.step(MechanicTickInputs.empty(dispatcher))

    assert result.committed.tolist() == [False]
    assert result.preflight.reason.tolist() == [reason]
    assert torch.equal(runtime.battle.entity_hp, hp_before)
    assert torch.equal(runtime.battle.rng.words, rng_before)
    assert runtime.events.count.tolist() == [0]


def test_death_damage_family_matches_python_while_death_spawn_row_fails_closed() -> (
    None
):
    battle = _battle()
    source = _spawn(battle, "Golem", 0, Position(9.0, 10.0))
    targets = [
        _spawn(battle, "Knight", 1, Position(8.0, 10.0)),
        _spawn(battle, "Knight", 1, Position(10.0, 10.0)),
    ]
    oracle = copy.deepcopy(battle)
    oracle_source = oracle.entities[source.id]
    _mechanic(oracle_source, "DeathDamage").on_death(oracle_source)
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=16, event_capacity=128
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    inputs = MechanicTickInputs.empty(dispatcher)
    inputs.death_triggered[0, _slot(runtime, source.id)] = True
    public = dispatcher.preflight(inputs)
    assert public.supported.tolist() == [False]
    assert public.reason.tolist() == [DispatchReason.UNSUPPORTED_OPCODE]

    dispatcher._dispatch_death_damage_(inputs)

    for target in targets:
        target_slot = _slot(runtime, target.id)
        oracle_target = oracle.entities[target.id]
        assert runtime.battle.entity_hp[0, target_slot].item() == (
            oracle_target.hitpoints
        )
        scalar_knockback = getattr(  # noqa: B009
            oracle_target, "_knockback_target"
        )
        assert scalar_knockback is not None
        assert dispatcher.knockback_target_units[0, target_slot].tolist() == [
            tiles_to_logic_units(scalar_knockback.x),
            tiles_to_logic_units(scalar_knockback.y),
        ]


def test_multiple_target_family_matches_python_while_spawn_area_row_fails_closed() -> (
    None
):
    battle = _battle()
    source = _spawn(battle, "ElectroWizard", 0, Position(9.0, 10.0))
    primary = _spawn(battle, "Knight", 1, Position(8.0, 10.0))
    secondary = _spawn(battle, "Knight", 1, Position(10.0, 10.0))
    source.target_id = primary.id
    oracle = copy.deepcopy(battle)
    oracle_source = oracle.entities[source.id]
    oracle_primary = oracle.entities[primary.id]
    oracle_secondary = oracle.entities[secondary.id]
    multiple = _mechanic(oracle_source, "MultipleTargetAttack")
    multiple.on_attack_start(oracle_source, oracle_primary)
    oracle_primary.take_damage(oracle_source.damage)
    _mechanic(oracle_source, "SerializedOnHitBuff").on_attack_hit(
        oracle_source, oracle_primary
    )
    multiple.resolve_secondary_attack_hits(
        oracle_source,
        oracle_primary,
        oracle_source.damage,
        oracle,
    )
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=16, event_capacity=128
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    source_slot = _slot(runtime, source.id)
    primary_slot = _slot(runtime, primary.id)
    secondary_slot = _slot(runtime, secondary.id)
    inputs = MechanicTickInputs.empty(dispatcher)
    inputs.connected_target_slot[0, source_slot] = primary_slot
    inputs.connected[0, source_slot] = True
    inputs.attack_started[0, source_slot] = True
    inputs.attack_source_slot[0, 0] = source_slot
    inputs.attack_target_slot[0, 0] = primary_slot
    inputs.attack_damage[0, 0] = source.damage
    inputs.attack_valid[0, 0] = True
    inputs.status_eligible[0, 0] = True
    public = dispatcher.preflight(inputs)
    assert public.supported.tolist() == [False]
    assert public.reason.tolist() == [DispatchReason.CHILD_MATERIALIZATION]

    dispatcher._step_candidate_(inputs)

    assert runtime.battle.entity_hp[0, primary_slot].item() == (
        oracle_primary.hitpoints
    )
    assert runtime.battle.entity_hp[0, secondary_slot].item() == (
        oracle_secondary.hitpoints
    )
    assert runtime.status.stun_timer[0, primary_slot].item() == (
        oracle_primary.stun_timer
    )
    assert runtime.status.stun_timer[0, secondary_slot].item() == (
        oracle_secondary.stun_timer
    )


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


def test_bandit_retained_charge_travel_and_damage_match_python_over_episode() -> None:
    battle = _battle()
    bandit = _spawn(battle, "Bandit", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Knight", 1, Position(12.0, 14.0))
    bandit.target_id = target.id
    oracle = copy.deepcopy(battle)
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=16, event_capacity=256
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    bandit_slot = _slot(runtime, bandit.id)
    target_slot = _slot(runtime, target.id)

    for _ in range(48):
        oracle_bandit = oracle.entities[bandit.id]
        oracle_target = oracle.entities[target.id]
        mechanic = _mechanic(oracle_bandit, "BanditDash")
        inputs = MechanicTickInputs.empty(dispatcher)
        inputs.connected_target_slot[0, bandit_slot] = target_slot
        inputs.connected[0, bandit_slot] = oracle_target.is_alive
        inputs.special_target_in_range[0, bandit_slot] = (
            oracle_target.is_alive
            and mechanic._target_edge_distance(oracle_bandit, oracle_target) is not None
        )
        inputs.attack_rate[0, bandit_slot] = oracle_bandit.get_attack_rate_multiplier()

        mechanic.on_tick(oracle_bandit, 50)
        mechanic.on_movement_tick(oracle_bandit, 50)
        result = dispatcher.step(inputs)

        assert result.committed.tolist() == [True]
        assert runtime.battle.entity_x_units[0, bandit_slot].item() == (
            tiles_to_logic_units(oracle_bandit.position.x)
        )
        assert runtime.battle.entity_y_units[0, bandit_slot].item() == (
            tiles_to_logic_units(oracle_bandit.position.y)
        )
        assert (
            runtime.battle.entity_hp[0, target_slot].item() == oracle_target.hitpoints
        )
        oracle.time += 0.05
        runtime.battle.time += 0.05
        if not getattr(oracle_bandit, "_bandit_dashing", False) and (
            oracle_target.hitpoints < target.hitpoints
        ):
            break
    else:
        pytest.fail("Bandit retained dash did not complete")


def test_bandit_mixed_dt_row_rejects_only_non_native_tick_atomically() -> None:
    battles: list[BattleState] = []
    ids: list[tuple[int, int]] = []
    for _ in range(2):
        battle = _battle()
        source = _spawn(battle, "Bandit", 0, Position(9.0, 10.0))
        target = _spawn(battle, "Knight", 1, Position(12.0, 14.0))
        source.target_id = target.id
        battles.append(battle)
        ids.append((source.id, target.id))
    runtime = TensorBattleRuntime.from_battles(battles, max_entities=16)
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, battles)
    inputs = MechanicTickInputs.empty(dispatcher)
    inputs.dt_ms[:] = torch.tensor([50, 100])
    for row, (source_id, target_id) in enumerate(ids):
        source_slot = _slot(runtime, source_id, row)
        inputs.connected_target_slot[row, source_slot] = _slot(runtime, target_id, row)
        inputs.connected[row, source_slot] = True
        inputs.special_target_in_range[row, source_slot] = True
    row_one_before = dispatcher.dash.phase[1].clone()

    result = dispatcher.step(inputs)

    assert result.committed.tolist() == [True, False]
    assert result.preflight.reason.tolist() == [
        DispatchReason.NONE,
        DispatchReason.INVALID_INPUT,
    ]
    assert torch.equal(dispatcher.dash.phase[1], row_one_before)


def test_bandit_native_dash_band_boundaries_follow_python_oracle() -> None:
    battles: list[BattleState] = []
    expected: list[bool] = []
    source_ids: list[int] = []
    target_ids: list[int] = []
    for distance in (3.999, 4.0, 6.5, 6.501):
        battle = _battle()
        source = _spawn(battle, "Bandit", 0, Position(9.0, 10.0))
        target = _spawn(battle, "Knight", 1, Position(9.0 + distance, 10.0))
        source.target_id = target.id
        mechanic = _mechanic(source, "BanditDash")
        expected.append(mechanic._target_edge_distance(source, target) is not None)
        source_ids.append(source.id)
        target_ids.append(target.id)
        battles.append(battle)
    runtime = TensorBattleRuntime.from_battles(battles, max_entities=16)
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, battles)
    inputs = MechanicTickInputs.empty(dispatcher)
    for row, accepted in enumerate(expected):
        source_slot = _slot(runtime, source_ids[row], row)
        inputs.connected_target_slot[row, source_slot] = _slot(
            runtime, target_ids[row], row
        )
        inputs.connected[row, source_slot] = True
        inputs.special_target_in_range[row, source_slot] = accepted

    result = dispatcher.step(inputs)

    assert result.committed.tolist() == [True] * len(battles)
    charging = dispatcher.dash.phase != 0
    assert [
        charging[row, _slot(runtime, source_ids[row], row)].item() for row in range(4)
    ] == expected


def test_bandit_travel_blocks_effects_but_post_landing_tail_blocks_only_damage() -> (
    None
):
    battle = _battle()
    source = _spawn(battle, "MiniSparkys", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Bandit", 1, Position(10.0, 10.0))
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=16, event_capacity=64
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    source_slot = _slot(runtime, source.id)
    target_slot = _slot(runtime, target.id)
    hp_before = runtime.battle.entity_hp[0, target_slot].item()

    dispatcher.dash.phase[0, target_slot] = 0
    dispatcher.dash.invulnerable_until_ms[0, target_slot] = 100.0
    inputs = MechanicTickInputs.empty(dispatcher)
    inputs.attack_source_slot[0, 0] = source_slot
    inputs.attack_target_slot[0, 0] = target_slot
    inputs.attack_damage[0, 0] = 10.0
    inputs.attack_valid[0, 0] = True
    inputs.status_eligible[0, 0] = True
    result = dispatcher.step(inputs)
    assert result.committed.tolist() == [True]
    assert runtime.battle.entity_hp[0, target_slot].item() == hp_before
    assert runtime.status.stun_timer[0, target_slot].item() > 0

    runtime.status.stun_timer[0, target_slot] = 0
    dispatcher.dash.phase[0, target_slot] = 2
    dispatcher.dash.position_units[0, target_slot] = torch.tensor([10_000, 10_000])
    dispatcher.dash.destination_units[0, target_slot] = torch.tensor([20_000, 10_000])
    result = dispatcher.step(inputs)
    assert result.committed.tolist() == [True]
    assert runtime.battle.entity_hp[0, target_slot].item() == hp_before
    assert runtime.status.stun_timer[0, target_slot].item() == 0


def test_underground_transport_frames_match_python_oracle() -> None:
    battle = _battle()
    miner = _spawn(battle, "Miner", 0, Position(12.0, 20.0), deployed=False)
    oracle = copy.deepcopy(battle)
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=16)
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    miner_slot = _slot(runtime, miner.id)

    for _ in range(80):
        oracle_miner = oracle.entities[miner.id]
        mechanic = _mechanic(oracle_miner, "UndergroundDeployment")
        destination = getattr(  # noqa: B009
            oracle_miner, "_underground_destination"
        )
        inputs = MechanicTickInputs.empty(dispatcher)
        inputs.underground_destination_units[0, miner_slot] = torch.tensor(
            [
                tiles_to_logic_units(destination.x),
                tiles_to_logic_units(destination.y),
            ]
        )
        inputs.deploy_delay_total_seconds[0, miner_slot] = (
            oracle_miner.placement_delay_total
        )
        inputs.deploy_delay_remaining_seconds[0, miner_slot] = (
            oracle_miner.deploy_delay_remaining
        )
        inputs.underground_travel_duration_seconds[0, miner_slot] = getattr(  # noqa: B009
            oracle_miner, "_underground_travel_duration"
        )

        mechanic.on_deploy_tick(oracle_miner, 50)
        result = dispatcher.step(inputs)

        assert result.committed.tolist() == [True]
        assert runtime.battle.entity_x_units[0, miner_slot].item() == (
            tiles_to_logic_units(oracle_miner.position.x)
        )
        assert runtime.battle.entity_y_units[0, miner_slot].item() == (
            tiles_to_logic_units(oracle_miner.position.y)
        )
        oracle_miner.deploy_delay_remaining = max(
            0.0, oracle_miner.deploy_delay_remaining - 0.05
        )
        if oracle_miner.position == destination:
            break
    else:
        pytest.fail("Miner underground transport did not reach destination")


def test_mega_knight_spawn_pushback_and_retained_leap_match_python() -> None:
    battle = _battle()
    mega = _spawn(battle, "MegaKnight", 0, Position(3.5, 10.0))
    target = _spawn(battle, "Knight", 1, Position(3.5, 15.0))
    mega.target_id = target.id
    oracle = copy.deepcopy(battle)
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=16, event_capacity=512
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    mega_slot = _slot(runtime, mega.id)
    target_slot = _slot(runtime, target.id)
    saw_slam = False

    for tick in range(48):
        oracle_mega = oracle.entities[mega.id]
        oracle_target = oracle.entities[target.id]
        leap = _mechanic(oracle_mega, "MegaKnightSlam")
        inputs = MechanicTickInputs.empty(dispatcher)
        inputs.connected_target_slot[0, mega_slot] = target_slot
        inputs.connected[0, mega_slot] = oracle_target.is_alive
        inputs.special_target_in_range[0, mega_slot] = (
            oracle_target.is_alive
            and leap._target_edge_distance(oracle_mega, oracle_target) is not None
        )
        inputs.attack_rate[0, mega_slot] = oracle_mega.get_attack_rate_multiplier()
        if tick == 0:
            inputs.spawned[0, mega_slot] = True
            leap.on_spawn(oracle_mega)
            _mechanic(oracle_mega, "SpawnPushback").on_spawn(oracle_mega)

        before_phase = getattr(oracle_mega, "_mk_leap_phase", None)
        leap.on_tick(oracle_mega, 50)
        leap.on_movement_tick(oracle_mega, 50)
        saw_slam |= (
            before_phase == "airborne"
            and getattr(oracle_mega, "_mk_leap_phase", None) != "airborne"
        )
        result = dispatcher.step(inputs)

        assert result.committed.tolist() == [True]
        assert runtime.battle.entity_x_units[0, mega_slot].item() == (
            tiles_to_logic_units(oracle_mega.position.x)
        )
        assert runtime.battle.entity_y_units[0, mega_slot].item() == (
            tiles_to_logic_units(oracle_mega.position.y)
        ), tick
        assert runtime.battle.entity_hp[0, target_slot].item() == (
            oracle_target.hitpoints
        )
        if saw_slam and getattr(oracle_mega, "_mk_leap_phase", None) is None:
            break
    else:
        pytest.fail("Mega Knight retained leap did not complete")


def test_mega_knight_spawn_slam_and_pushback_match_python() -> None:
    battle = _battle()
    mega = _spawn(battle, "MegaKnight", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Knight", 1, Position(10.0, 10.0))
    oracle = copy.deepcopy(battle)
    oracle_mega = oracle.entities[mega.id]
    oracle_target = oracle.entities[target.id]
    _mechanic(oracle_mega, "MegaKnightSlam").on_spawn(oracle_mega)
    _mechanic(oracle_mega, "SpawnPushback").on_spawn(oracle_mega)
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=16, event_capacity=128
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    mega_slot = _slot(runtime, mega.id)
    target_slot = _slot(runtime, target.id)
    inputs = MechanicTickInputs.empty(dispatcher)
    inputs.spawned[0, mega_slot] = True

    result = dispatcher.step(inputs)

    assert result.committed.tolist() == [True]
    assert runtime.battle.entity_hp[0, target_slot].item() == oracle_target.hitpoints
    scalar_knockback = getattr(  # noqa: B009
        oracle_target, "_knockback_target"
    )
    assert scalar_knockback is not None
    assert dispatcher.knockback_target_units[0, target_slot].tolist() == [
        tiles_to_logic_units(scalar_knockback.x),
        tiles_to_logic_units(scalar_knockback.y),
    ]


def test_fisherman_retained_windup_flight_and_drag_match_python() -> None:
    battle = _battle()
    fisherman = _spawn(battle, "Fisherman", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Knight", 1, Position(9.0, 16.0))
    fisherman.target_id = target.id
    oracle = copy.deepcopy(battle)
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=16, event_capacity=256
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    source_slot = _slot(runtime, fisherman.id)
    target_slot = _slot(runtime, target.id)
    started = False

    for _ in range(64):
        oracle_source = oracle.entities[fisherman.id]
        oracle_target = oracle.entities[target.id]
        mechanic = _mechanic(oracle_source, "FishermanHook")
        launch, _, _ = oracle_source._projectile_launch_geometry(oracle_target)
        inputs = MechanicTickInputs.empty(dispatcher)
        inputs.connected_target_slot[0, source_slot] = target_slot
        inputs.connected[0, source_slot] = oracle_target.is_alive
        inputs.special_target_in_range[0, source_slot] = (
            mechanic._is_hook_target_in_range(oracle_source, oracle_target)
        )
        inputs.special_target_plane_valid[0, source_slot] = (
            oracle_source.can_affect_target_plane(oracle_target)
        )
        inputs.special_target_can_forced_move[0, source_slot] = (
            oracle_target.can_receive_forced_movement("Fisherman", "hook")
        )
        inputs.special_move_allowed[0, source_slot] = True
        inputs.special_launch_position_units[0, source_slot] = torch.tensor(
            [tiles_to_logic_units(launch.x), tiles_to_logic_units(launch.y)]
        )
        inputs.attack_rate[0, source_slot] = oracle_source.get_attack_rate_multiplier()

        mechanic.on_tick(oracle_source, 50)
        mechanic.on_object_tick(oracle_source, 50)
        started |= mechanic.state != "idle"
        result = dispatcher.step(inputs)

        assert result.committed.tolist() == [True]
        assert runtime.battle.entity_x_units[0, source_slot].item() == (
            tiles_to_logic_units(oracle_source.position.x)
        )
        assert runtime.battle.entity_y_units[0, source_slot].item() == (
            tiles_to_logic_units(oracle_source.position.y)
        )
        assert runtime.battle.entity_x_units[0, target_slot].item() == (
            tiles_to_logic_units(oracle_target.position.x)
        )
        assert runtime.battle.entity_y_units[0, target_slot].item() == (
            tiles_to_logic_units(oracle_target.position.y)
        )
        if started and mechanic.state == "idle":
            break
    else:
        pytest.fail("Fisherman retained hook did not complete")


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_transactional_dispatch_smoke() -> None:
    battle = _battle()
    source = _spawn(battle, "Bandit", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Knight", 1, Position(12.0, 14.0))
    source.target_id = target.id
    runtime = TensorBattleRuntime.from_battles(
        [battle], device="cuda", max_entities=8, event_capacity=32
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    inputs = MechanicTickInputs.empty(dispatcher)
    source_slot = _slot(runtime, source.id)
    inputs.connected_target_slot[0, source_slot] = _slot(runtime, target.id)
    inputs.connected[0, source_slot] = True
    inputs.special_target_in_range[0, source_slot] = True

    result = dispatcher.step(inputs)

    assert result.committed.item()
    assert dispatcher.dash.phase[0, source_slot].item() != 0
    assert runtime.events.count.device.type == "cuda"
