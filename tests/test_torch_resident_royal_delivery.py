from __future__ import annotations

import random
from collections import deque
from dataclasses import fields

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, SpawnProjectile, Troop
from clasher.spells import SPELL_REGISTRY
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_royal_delivery import (
    RoyalDeliveryMaterializeResult,
    TensorResidentRoyalDelivery,
)
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TickPhase


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _battle(seed: int = 991_200) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    target = Position(9.0, 10.0)
    for name, position in (
        ("Knight", target),
        ("MegaMinion", Position(10.0, 10.0)),
    ):
        stats = battle.card_loader.get_card(name)
        assert stats is not None
        battle._spawn_unit_at_position(
            position,
            1,
            stats,
            deploy_delay_override=0.0,
            snap_to_valid=False,
        )
        entity = battle.entities[battle.next_entity_id - 1]
        entity.stun_timer = 100.0
        entity.attack_cooldown = 10.0
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    cannon = battle._spawn_entity(Building, target, 1, cannon_stats)
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    cannon.stun_timer = 100.0
    cannon.attack_cooldown = 10.0
    player = battle.players[0]
    player.hand = ["RoyalDelivery", "Knight", "Cannon", "Fireball"]
    player.deck = [card for card in player.hand if card is not None]
    player.cycle_queue = deque()
    player.elixir = 10.0
    return battle


def _owners(
    battle: BattleState,
    device: str,
    *,
    max_entities: int = 16,
    event_capacity: int = 64,
) -> tuple[TensorResidentEngine, TensorResidentRoyalDelivery]:
    engine = TensorResidentEngine.from_battles(
        [battle.clone()],
        device=device,
        max_entities=max_entities,
        max_objects=8,
        event_capacity=event_capacity,
    )
    owner = TensorResidentRoyalDelivery.from_battles(
        engine.runtime,
        [battle],
        capacity=2,
    )
    return engine, owner


def _materialize(
    engine: TensorResidentEngine,
    owner: TensorResidentRoyalDelivery,
) -> RoyalDeliveryMaterializeResult:
    runtime = engine.runtime
    return owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor(
            [runtime.battle.card_to_id["RoyalDelivery"]],
            dtype=torch.int64,
            device=runtime.device,
        ),
        player_ids=torch.tensor([0], dtype=torch.int64, device=runtime.device),
        target_x_units=torch.tensor([9_000], dtype=torch.int64, device=runtime.device),
        target_y_units=torch.tensor([10_000], dtype=torch.int64, device=runtime.device),
        valid=torch.tensor([True], dtype=torch.bool, device=runtime.device),
    )


def test_full_delivery_lifecycle_matches_scalar_damage_planes_child_and_events(
    tensor_device: str,
) -> None:
    source = _battle()
    oracle = source.clone()
    assert SPELL_REGISTRY["RoyalDelivery"].cast(oracle, 0, Position(9.0, 10.0))
    scalar_carrier = next(
        entity
        for entity in oracle.entities.values()
        if isinstance(entity, SpawnProjectile)
    )
    engine, owner = _owners(source, tensor_device)
    royal_delivery_id = engine.runtime.battle.card_to_id["RoyalDelivery"]
    engine.runtime.events.append(
        phase=TickPhase.COMMANDS,
        opcode=RuntimeEventOpcode.COMMAND,
        valid=torch.ones((1, 1), dtype=torch.bool, device=engine.runtime.device),
        x_units=9_000,
        y_units=10_000,
        payload=royal_delivery_id,
    )

    materialized = _materialize(engine, owner)

    assert materialized.committed.tolist() == [True]
    assert materialized.carrier_entity_id.item() == scalar_carrier.id == 4
    carrier_slot = engine.runtime.battle.entity_id[0].tolist().index(scalar_carrier.id)
    assert engine.runtime.battle.entity_kind[0, carrier_slot].item() == 2
    assert engine.runtime.battle.entity_card[0, carrier_slot].item() == 0
    assert engine.runtime.battle.entity_hp[0, carrier_slot].item() == 1.0
    assert engine.runtime.battle.entity_hp_integer_kind[0, carrier_slot].item()
    assert owner.card_id[0, 0].item() == royal_delivery_id
    assert engine.runtime.events.count.item() == 2
    assert engine.runtime.events.phase[0, :2].tolist() == [
        TickPhase.COMMANDS,
        TickPhase.COMMANDS,
    ]
    assert engine.runtime.events.opcode[0, :2].tolist() == [
        RuntimeEventOpcode.COMMAND,
        RuntimeEventOpcode.PROJECTILE,
    ]
    assert engine.runtime.events.source_id[0, :2].tolist() == [0, 0]
    assert engine.runtime.events.target_id[0, :2].tolist() == [
        0,
        scalar_carrier.id,
    ]
    assert engine.runtime.events.payload[0, :2].tolist() == [
        royal_delivery_id,
        royal_delivery_id,
    ]
    assert owner.remaining_ms[0, 0].item() == 2_050
    assert (
        owner.catalog.travel_speed_units[
            engine.runtime.battle.card_to_id["RoyalDelivery"]
        ].item()
        == 5_000
    )

    impact = None
    for _ in range(40):
        oracle.step_logic_ticks(1)
        impact = owner.step_(engine.runtime, dt_ms=50)
        assert impact.committed.tolist() == [True]
        assert impact.impacted.tolist() == [False]
    assert owner.remaining_ms[0, 0].item() == 50
    assert owner.elapsed_ms[0, 0].item() == 2_000
    assert owner.travel_work_units[0, 0].item() == 200_000

    oracle.step_logic_ticks(1)
    impact = owner.step_(engine.runtime, dt_ms=50)
    assert impact.committed.tolist() == [True]
    assert impact is not None and impact.impacted.tolist() == [True]

    recruit = next(
        entity
        for entity in oracle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "DeliveryRecruit"
    )
    runtime = engine.runtime
    live_ids = runtime.battle.entity_id[0][runtime.entity_pool.active[0]].tolist()
    assert live_ids == [1, 2, 3, recruit.id]
    recruit_slot = runtime.battle.entity_id[0].tolist().index(recruit.id)
    assert (
        runtime.battle.card_names[
            int(runtime.battle.entity_card[0, recruit_slot].item())
        ]
        == "DeliveryRecruit"
    )
    assert runtime.battle.entity_hp[0, recruit_slot].item() == recruit.hitpoints == 547
    assert runtime.battle.entity_max_hp[0, recruit_slot].item() == 547
    assert (
        runtime.battle.entity_deploy_delay[0, recruit_slot].item()
        == pytest.approx(recruit.deploy_delay_remaining)
        == pytest.approx(0.20)
    )
    assert runtime.battle.entity_placement_pending[0, recruit_slot].item()
    assert runtime.phases.target_slot[0, recruit_slot].item() == -1
    assert not runtime.phases.waypoint_valid[0, recruit_slot].item()
    assert runtime.phases.movement_vector_count[0, recruit_slot].item() == 0
    assert owner.shield_hitpoints[0, recruit_slot].item() == 240

    for entity_id in (1, 2):
        scalar = oracle.entities[entity_id]
        slot = runtime.battle.entity_id[0].tolist().index(entity_id)
        assert runtime.battle.entity_hp[0, slot].item() == scalar.hitpoints
    cannon_slot = runtime.battle.entity_id[0].tolist().index(3)
    assert (
        runtime.battle.entity_hp[0, cannon_slot].item() == source.entities[3].hitpoints
    )
    assert impact.damage[0, cannon_slot].item() == 0.0
    assert not impact.pushback_active.any()

    count = int(runtime.events.count.item())
    assert runtime.events.opcode[0, :count].tolist() == [
        RuntimeEventOpcode.COMMAND,
        RuntimeEventOpcode.PROJECTILE,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.SPAWN,
    ]
    assert runtime.events.phase[0, :count].tolist() == [
        TickPhase.COMMANDS,
        TickPhase.COMMANDS,
        TickPhase.OBJECTS,
        TickPhase.OBJECTS,
        TickPhase.OBJECTS,
    ]
    assert runtime.events.target_id[0, 2:4].tolist() == [1, 2]


def test_clone_fork_and_selective_reset_own_independent_mutable_state(
    tensor_device: str,
) -> None:
    battles = [_battle(991_210), _battle(991_211)]
    engine = TensorResidentEngine.from_battles(
        [battle.clone() for battle in battles],
        device=tensor_device,
        max_entities=16,
        max_objects=8,
    )
    owner = TensorResidentRoyalDelivery.from_battles(
        engine.runtime, battles, capacity=2
    )
    owner.active[0, 0] = True
    owner.entity_id[0, 0] = 77
    cloned = owner.clone()
    forked = owner.fork([1])
    cloned.entity_id[0, 0] = 99

    assert owner.entity_id[0, 0].item() == 77
    assert forked.batch_size == 1
    assert forked.catalog is owner.catalog
    destination = owner.clone()
    destination.entity_id.fill_(123)
    destination.reset_rows_([0], owner, [1])
    assert destination.entity_id[0].tolist() == owner.entity_id[1].tolist()
    assert destination.entity_id[1].tolist() == [123, 123]


def test_serialized_and_synthetic_pushback_planes_are_data_driven(
    tensor_device: str,
) -> None:
    battle = _battle(991_220)
    engine, owner = _owners(battle, tensor_device)
    _materialize(engine, owner)
    card = engine.runtime.battle.card_to_id["RoyalDelivery"]
    assert owner.catalog.pushback_units[card].item() == 0
    owner.catalog.pushback_units[card] = 1_000
    owner.remaining_ms[0, 0] = 50

    result = owner.step_(engine.runtime, dt_ms=50)

    knight_slot = engine.runtime.battle.entity_id[0].tolist().index(1)
    assert result.committed.tolist() == [True]
    assert owner.pushback_active[0, knight_slot].item()
    assert owner.pushback_velocity_work[0, knight_slot].item() == 225
    assert owner.pushback_target_units[0, knight_slot].tolist() == [8_000, 10_000]


def test_impact_capacity_failure_rolls_back_timer_damage_ids_and_events(
    tensor_device: str,
) -> None:
    battle = _battle(991_230)
    engine, owner = _owners(
        battle,
        tensor_device,
        max_entities=4,
        event_capacity=64,
    )
    materialized = _materialize(engine, owner)
    assert materialized.committed.tolist() == [True]
    owner.remaining_ms[0, 0] = 50
    runtime_before = {
        descriptor.name: getattr(engine.runtime.battle, descriptor.name).clone()
        for descriptor in fields(engine.runtime.battle)
        if isinstance(getattr(engine.runtime.battle, descriptor.name), torch.Tensor)
    }
    owner_before = owner.clone()
    events_before = engine.runtime.events.count.clone()
    next_id_before = engine.runtime.entity_pool.next_entity_id.clone()

    result = owner.step_(engine.runtime, dt_ms=50)

    assert result.committed.tolist() == [False]
    assert result.impacted.tolist() == [False]
    assert torch.equal(engine.runtime.events.count, events_before)
    assert torch.equal(engine.runtime.entity_pool.next_entity_id, next_id_before)
    for name, expected in runtime_before.items():
        assert torch.equal(getattr(engine.runtime.battle, name), expected), name
    for descriptor in fields(owner):
        actual = getattr(owner, descriptor.name)
        expected = getattr(owner_before, descriptor.name)
        if isinstance(actual, torch.Tensor):
            assert torch.equal(actual, expected), descriptor.name


def test_materialization_capacity_failure_is_atomic(tensor_device: str) -> None:
    battle = _battle(991_240)
    engine, owner = _owners(battle, tensor_device, max_entities=3)
    runtime_before = {
        descriptor.name: getattr(engine.runtime.battle, descriptor.name).clone()
        for descriptor in fields(engine.runtime.battle)
        if isinstance(getattr(engine.runtime.battle, descriptor.name), torch.Tensor)
    }
    next_id_before = engine.runtime.entity_pool.next_entity_id.clone()
    events_before = engine.runtime.events.count.clone()

    result = _materialize(engine, owner)

    assert result.committed.tolist() == [False]
    assert result.accepted.tolist() == [False]
    assert result.capacity_rejected.tolist() == [True]
    assert not owner.active.any()
    assert torch.equal(engine.runtime.events.count, events_before)
    assert torch.equal(engine.runtime.entity_pool.next_entity_id, next_id_before)
    for name, expected in runtime_before.items():
        assert torch.equal(getattr(engine.runtime.battle, name), expected), name
