from __future__ import annotations

import copy
from dataclasses import fields

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, TimedExplosive, Troop
from clasher.torch_sim.resident_timed_explosions import (
    TensorTimedExplosionTargets,
    TimedExplosionReason,
    resolve_timed_terminal_explosions_,
)
from clasher.torch_sim.resident_timed_terminal_payloads import (
    TensorTimedTerminalEvents,
)
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TensorBattleRuntime

TIMED_ROOTS = ("Balloon", "BombTower", "SkeletonBarrel")


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Entity:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = battle._spawn_entity(Troop, position, player, stats)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _timed_battle(root: str) -> tuple[BattleState, TimedExplosive]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    parent = _spawn(battle, root, 0, Position(9.0, 10.0))
    parent.take_damage(parent.hitpoints)
    battle._cleanup_dead_entities()
    explosives = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, TimedExplosive)
    ]
    assert len(explosives) == 1
    return battle, explosives[0]


def _spawn_building(
    battle: BattleState, name: str, player: int, position: Position
) -> Entity:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = battle._spawn_entity(Building, position, player, stats)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _slot(runtime: TensorBattleRuntime, entity_id: int, row: int = 0) -> int:
    match = torch.nonzero(
        runtime.battle.entity_id[row] == entity_id, as_tuple=False
    ).flatten()
    assert match.numel() == 1
    return int(match.item())


def _terminals(
    runtime: TensorBattleRuntime,
    explosives: list[TimedExplosive],
) -> TensorTimedTerminalEvents:
    device = runtime.device
    batch = torch.arange(len(explosives), dtype=torch.int64, device=device)
    object_slot = torch.tensor(
        [_slot(runtime, explosive.id, row) for row, explosive in enumerate(explosives)],
        dtype=torch.int64,
        device=device,
    )
    integer = lambda values, dtype=torch.int64: torch.tensor(
        values, dtype=dtype, device=device
    )
    return TensorTimedTerminalEvents(
        batch_index=batch,
        object_slot=object_slot,
        object_id=integer([item.id for item in explosives]),
        operation_row=torch.zeros_like(batch),
        player=integer([item.player_id for item in explosives], torch.int8),
        x_units=integer(
            [round(item.position.x * 1_000) for item in explosives], torch.int32
        ),
        y_units=integer(
            [round(item.position.y * 1_000) for item in explosives], torch.int32
        ),
        damage=torch.tensor(
            [item.explosion_damage for item in explosives],
            dtype=torch.float64,
            device=device,
        ),
        radius_units=integer(
            [round(item.explosion_radius * 1_000) for item in explosives], torch.int32
        ),
        knockback_units=integer(
            [round(item.knockback_distance * 1_000) for item in explosives], torch.int32
        ),
        child_row=torch.full_like(batch, -1),
        child_count=integer(
            [item.death_spawn_count for item in explosives], torch.int16
        ),
        facing_x_units=torch.zeros_like(batch, dtype=torch.int32),
        facing_y_units=torch.zeros_like(batch, dtype=torch.int32),
        freeze_expiry_time=torch.zeros_like(batch, dtype=torch.float64),
    )


@pytest.mark.parametrize("root", TIMED_ROOTS)
def test_enabled_timed_explosion_matches_scalar_targeting_damage_and_knockback(
    root: str,
) -> None:
    source, explosive = _timed_battle(root)
    targets = [
        _spawn(source, "Knight", 1, Position(9.0, 10.0)),
        _spawn(source, "Minions", 1, Position(10.0, 10.0)),
        _spawn(source, "Knight", 1, Position(13.6, 10.0)),
        _spawn(source, "Knight", 0, Position(9.5, 10.0)),
    ]
    oracle = copy.deepcopy(source)
    oracle_explosive = oracle.entities[explosive.id]
    assert isinstance(oracle_explosive, TimedExplosive)
    oracle_explosive._explode(oracle)

    runtime = TensorBattleRuntime.from_battles(
        [source], max_entities=16, event_capacity=64
    )
    terminal = _terminals(runtime, [explosive])
    traits = TensorTimedExplosionTargets.from_battles(
        runtime,
        [source],
        terminal,
        source_kinds=[explosive.card_stats.name],
    )
    result = resolve_timed_terminal_explosions_(runtime, terminal, traits)

    assert result.committed.tolist() == [True]
    for target in targets:
        slot = _slot(runtime, target.id)
        assert (
            runtime.battle.entity_hp[0, slot].item()
            == oracle.entities[target.id].hitpoints
        )
    scalar_knockback = getattr(oracle.entities[targets[0].id], "_knockback_target")  # noqa: B009
    descriptors = result.knockback.valid[0]
    if scalar_knockback is None:
        assert not descriptors.any().item()
    else:
        lane = torch.nonzero(
            descriptors & (result.knockback.target_id[0] == targets[0].id),
            as_tuple=False,
        ).flatten()
        assert lane.numel() == 1
        assert result.knockback.target_units[0, int(lane.item())].tolist() == [
            round(scalar_knockback.x * 1_000),
            round(scalar_knockback.y * 1_000),
        ]


def test_whole_hit_shield_and_strict_tangent_geometry_match_scalar() -> None:
    source, explosive = _timed_battle("Balloon")
    shielded = _spawn(source, "Guards", 1, Position(9.0, 10.0))
    tangent = _spawn(
        source,
        "Knight",
        1,
        Position(9.0 + explosive.explosion_radius + 0.5, 10.0),
    )
    oracle = copy.deepcopy(source)
    oracle_explosive = oracle.entities[explosive.id]
    assert isinstance(oracle_explosive, TimedExplosive)
    oracle_explosive._explode(oracle)
    runtime = TensorBattleRuntime.from_battles([source], max_entities=16)
    terminal = _terminals(runtime, [explosive])
    traits = TensorTimedExplosionTargets.from_battles(
        runtime, [source], terminal, source_kinds=[explosive.card_stats.name]
    )

    result = resolve_timed_terminal_explosions_(runtime, terminal, traits)

    shield_slot = _slot(runtime, shielded.id)
    tangent_slot = _slot(runtime, tangent.id)
    oracle_shield = next(
        mechanic
        for mechanic in oracle.entities[shielded.id].mechanics
        if type(mechanic).__name__ == "Shield"
    )
    assert runtime.battle.entity_hp[0, shield_slot].item() == shielded.hitpoints
    assert (
        traits.shield_current[0, shield_slot].item()
        == vars(oracle_shield)["current_shield"]
    )
    assert result.shield_absorbed.any().item()
    assert runtime.battle.entity_hp[0, tangent_slot].item() == tangent.hitpoints


def test_building_square_hitbox_and_air_plane_are_data_driven() -> None:
    source, explosive = _timed_battle("Balloon")
    building = _spawn_building(source, "Cannon", 1, Position(12.4, 11.0))
    airborne = _spawn(source, "BabyDragon", 1, Position(9.0, 10.0))
    airborne.is_air_unit = True
    runtime = TensorBattleRuntime.from_battles([source], max_entities=16)
    terminal = _terminals(runtime, [explosive])
    traits = TensorTimedExplosionTargets.from_battles(
        runtime, [source], terminal, source_kinds=[explosive.card_stats.name]
    )

    result = resolve_timed_terminal_explosions_(
        runtime, terminal, traits, hits_air=False, hits_ground=True
    )

    assert result.committed.tolist() == [True]
    assert runtime.battle.entity_hp[0, _slot(runtime, building.id)] < building.hitpoints
    assert (
        runtime.battle.entity_hp[0, _slot(runtime, airborne.id)] == airborne.hitpoints
    )


def test_damage_death_events_are_id_stable_after_physical_slot_permutation() -> None:
    source, explosive = _timed_battle("Balloon")
    lethal = _spawn(source, "Knight", 1, Position(9.0, 10.0))
    survivor = _spawn(source, "Knight", 1, Position(10.0, 10.0))
    lethal.hitpoints = 1
    runtime = TensorBattleRuntime.from_battles(
        [source], max_entities=8, event_capacity=16
    )
    terminal = _terminals(runtime, [explosive])
    traits = TensorTimedExplosionTargets.from_battles(
        runtime, [source], terminal, source_kinds=[explosive.card_stats.name]
    )
    permutation = torch.tensor([2, 0, 1, 3, 4, 5, 6, 7])
    for descriptor in fields(runtime.battle):
        value = getattr(runtime.battle, descriptor.name)
        if (
            isinstance(value, torch.Tensor)
            and descriptor.name.startswith("entity_")
            and value.ndim >= 2
            and value.shape[1] == runtime.max_entities
        ):
            value.copy_(value[:, permutation])
    runtime.entity_pool.active.copy_(runtime.entity_pool.active[:, permutation])
    for descriptor in fields(traits):
        value = getattr(traits, descriptor.name)
        if value.shape[-1] == runtime.max_entities:
            value.copy_(value[..., permutation])

    result = resolve_timed_terminal_explosions_(runtime, terminal, traits)

    assert result.committed.tolist() == [True]
    width = int(runtime.events.count[0].item())
    assert runtime.events.opcode[0, :width].tolist() == [
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
        RuntimeEventOpcode.DAMAGE,
    ]
    assert runtime.events.target_id[0, :width].tolist() == [
        lethal.id,
        lethal.id,
        survivor.id,
    ]


def test_event_capacity_rolls_back_only_overflowing_row() -> None:
    first, first_explosive = _timed_battle("Balloon")
    second, second_explosive = _timed_battle("Balloon")
    first_target = _spawn(first, "Knight", 1, Position(9.0, 10.0))
    second_target = _spawn(second, "Knight", 1, Position(9.0, 10.0))
    runtime = TensorBattleRuntime.from_battles(
        [first, second], max_entities=8, event_capacity=2
    )
    runtime.events.append(
        phase=0,
        opcode=RuntimeEventOpcode.AREA,
        valid=torch.tensor([[True, True], [False, False]]),
    )
    terminal = _terminals(runtime, [first_explosive, second_explosive])
    traits = TensorTimedExplosionTargets.from_battles(
        runtime,
        [first, second],
        terminal,
        source_kinds=[
            first_explosive.card_stats.name,
            second_explosive.card_stats.name,
        ],
    )
    before = runtime.battle.entity_hp.clone()

    result = resolve_timed_terminal_explosions_(runtime, terminal, traits)

    assert result.committed.tolist() == [False, True]
    assert result.reason.tolist() == [TimedExplosionReason.EVENT_CAPACITY, 0]
    assert torch.equal(runtime.battle.entity_hp[0], before[0])
    assert (
        runtime.battle.entity_hp[1, _slot(runtime, second_target.id, 1)]
        < before[1, _slot(runtime, second_target.id, 1)]
    )
    assert (
        runtime.battle.entity_hp[0, _slot(runtime, first_target.id, 0)]
        == before[0, _slot(runtime, first_target.id, 0)]
    )


def test_lethal_serialized_death_payload_is_atomic_fail_closed() -> None:
    source, explosive = _timed_battle("Balloon")
    victim = _spawn(source, "Golem", 1, Position(9.0, 10.0))
    victim.hitpoints = 1
    runtime = TensorBattleRuntime.from_battles([source], max_entities=8)
    terminal = _terminals(runtime, [explosive])
    traits = TensorTimedExplosionTargets.from_battles(
        runtime, [source], terminal, source_kinds=[explosive.card_stats.name]
    )
    before_hp = runtime.battle.entity_hp.clone()
    before_events = runtime.events.count.clone()

    result = resolve_timed_terminal_explosions_(runtime, terminal, traits)

    assert result.committed.tolist() == [False]
    assert result.reason.tolist() == [TimedExplosionReason.UNSUPPORTED_DEATH_PAYLOAD]
    assert torch.equal(runtime.battle.entity_hp, before_hp)
    assert torch.equal(runtime.events.count, before_events)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_resolution_matches_cpu() -> None:
    cpu_battle, cpu_explosive = _timed_battle("SkeletonBarrel")
    _spawn(cpu_battle, "Knight", 1, Position(9.0, 10.0))
    cuda_battle = copy.deepcopy(cpu_battle)
    cuda_explosive = cuda_battle.entities[cpu_explosive.id]
    assert isinstance(cuda_explosive, TimedExplosive)
    cpu_runtime = TensorBattleRuntime.from_battles([cpu_battle], max_entities=8)
    cuda_runtime = TensorBattleRuntime.from_battles(
        [cuda_battle], max_entities=8, device="cuda"
    )
    cpu_terminal = _terminals(cpu_runtime, [cpu_explosive])
    cuda_terminal = _terminals(cuda_runtime, [cuda_explosive])
    cpu_traits = TensorTimedExplosionTargets.from_battles(
        cpu_runtime,
        [cpu_battle],
        cpu_terminal,
        source_kinds=[cpu_explosive.card_stats.name],
    )
    cuda_traits = TensorTimedExplosionTargets.from_battles(
        cuda_runtime,
        [cuda_battle],
        cuda_terminal,
        source_kinds=[cuda_explosive.card_stats.name],
    )

    cpu_result = resolve_timed_terminal_explosions_(
        cpu_runtime, cpu_terminal, cpu_traits
    )
    cuda_result = resolve_timed_terminal_explosions_(
        cuda_runtime, cuda_terminal, cuda_traits
    )

    assert torch.equal(
        cuda_runtime.battle.entity_hp.cpu(), cpu_runtime.battle.entity_hp
    )
    assert torch.equal(cuda_result.hit.cpu(), cpu_result.hit)
    assert torch.equal(cuda_result.knockback.valid.cpu(), cpu_result.knockback.valid)
    assert torch.equal(
        cuda_result.knockback.target_units.cpu(),
        cpu_result.knockback.target_units,
    )
