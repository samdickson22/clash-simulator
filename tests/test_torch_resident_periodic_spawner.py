from __future__ import annotations

import copy
from dataclasses import fields
from functools import lru_cache
from typing import cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
from clasher.mechanics.shared.spawner import PeriodicSpawner
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.oracle_event_capture import (
    OracleEventRecord,
    PythonOracleEventCapture,
)
from clasher.torch_sim.resident_periodic_spawner import (
    PeriodicSpawnerReason,
    TensorPeriodicSpawnerCatalog,
    TensorPeriodicSpawnerRuntimeState,
    step_runtime_periodic_spawners_,
)
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)

ROOTS = ("NightWitch", "Tombstone", "Witch")


@lru_cache(maxsize=2)
def _catalog(device: str) -> TensorPeriodicSpawnerCatalog:
    battle = BattleState()
    names = tuple(sorted(set(unique_cards_from_decks(load_deck_pool()))))
    cards = TensorCardCatalog.compile(battle.card_loader, names, device=device)
    return TensorPeriodicSpawnerCatalog.compile(battle.card_loader, cards, names)


def _battle(root: str, *, x: float = 9.0) -> tuple[BattleState, Entity]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(root)
    assert stats is not None
    entity_type = Building if str(stats.card_type).casefold() == "building" else Troop
    source = battle._spawn_entity(entity_type, Position(x, 10.0), 0, stats)
    source.deploy_delay_remaining = 0.0
    source.placement_pending = False
    source._spawn_hook_pending = False
    source._spawn_hook_fired = True
    source._facing_x_units = 300
    source._facing_y_units = 400
    return battle, source


def _mechanic(entity: Entity) -> PeriodicSpawner:
    return next(
        cast(PeriodicSpawner, mechanic)
        for mechanic in entity.mechanics
        if isinstance(mechanic, PeriodicSpawner)
    )


def _runtime(
    battle: BattleState,
    *,
    device: str,
    event_capacity: int = 64,
) -> tuple[
    TensorBattleRuntime,
    TensorPeriodicSpawnerRuntimeState,
    TensorPeriodicSpawnerCatalog,
]:
    catalog = _catalog(device)
    runtime = TensorBattleRuntime.from_battles(
        [battle],
        device=device,
        max_entities=32,
        event_capacity=event_capacity,
        catalog=catalog.cards,
    )
    catalog.prepare_runtime(runtime)
    return runtime, TensorPeriodicSpawnerRuntimeState.zeros(runtime), catalog


def _represented(
    runtime: TensorBattleRuntime,
) -> list[tuple[int, str, int, int, float]]:
    result: list[tuple[int, str, int, int, float]] = []
    for slot in range(runtime.max_entities):
        if not runtime.entity_pool.active[0, slot]:
            continue
        card = runtime.battle.card_names[int(runtime.battle.entity_card[0, slot])]
        result.append(
            (
                int(runtime.battle.entity_id[0, slot]),
                card,
                int(runtime.battle.entity_x_units[0, slot]),
                int(runtime.battle.entity_y_units[0, slot]),
                float(runtime.battle.entity_hp[0, slot]),
            )
        )
    return sorted(result)


def _oracle(battle: BattleState) -> list[tuple[int, str, int, int, float]]:
    return [
        (
            entity_id,
            str(entity.card_stats.name),
            round(entity.position.x * 1_000),
            round(entity.position.y * 1_000),
            float(entity.hitpoints),
        )
        for entity_id, entity in sorted(battle.entities.items())
    ]


def _tensor_events(
    runtime: TensorBattleRuntime, start: int = 0
) -> list[tuple[int, int, int, int, int, int, float, int]]:
    return [
        (
            int(runtime.events.phase[0, slot].item()),
            int(runtime.events.opcode[0, slot].item()),
            int(runtime.events.source_id[0, slot].item()),
            int(runtime.events.target_id[0, slot].item()),
            int(runtime.events.x_units[0, slot].item()),
            int(runtime.events.y_units[0, slot].item()),
            float(runtime.events.amount[0, slot].item()),
            int(runtime.events.payload[0, slot].item()),
        )
        for slot in range(start, int(runtime.events.count[0].item()))
    ]


def _oracle_events(
    records: list[OracleEventRecord], runtime: TensorBattleRuntime
) -> list[tuple[int, int, int, int, int, int, float, int]]:
    return [
        (
            record.phase,
            record.opcode,
            record.source_id,
            record.target_id,
            record.x_units,
            record.y_units,
            float(record.amount),
            runtime.battle.card_to_id[str(record.payload)],
        )
        for record in records
    ]


@pytest.mark.parametrize("root", ROOTS)
@pytest.mark.parametrize(
    "device",
    [
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ],
)
def test_serialized_wave_timers_and_materialized_children_match_oracle(
    root: str,
    device: str,
) -> None:
    source, entity = _battle(root)
    oracle = copy.deepcopy(source)
    oracle_source = oracle.entities[entity.id]
    mechanic = _mechanic(oracle_source)
    runtime, state, catalog = _runtime(source, device=device)
    periodic_row = int(
        catalog.source_row_by_card[
            runtime.card_catalog_index[runtime.battle.entity_card[0, 0]]
        ].item()
    )
    timeline = [int(catalog.spawn.first_spawn_delay_ms[periodic_row].item())]
    timeline.extend(
        [int(catalog.spawn.intra_spawn_interval_ms[periodic_row].item())]
        * (int(catalog.spawn.count[periodic_row].item()) - 1)
    )
    facing_x = torch.zeros_like(runtime.battle.entity_x_units)
    facing_y = torch.zeros_like(runtime.battle.entity_y_units)
    facing_x[0, 0] = 300
    facing_y[0, 0] = 400
    rng_before = runtime.battle.rng.words.clone(), runtime.battle.rng.index.clone()

    with PythonOracleEventCapture(oracle) as capture:
        oracle_event_start = 0
        for dt_ms in timeline:
            tensor_event_start = int(runtime.events.count[0].item())
            with capture._scope(phase=TickPhase.OBJECTS):
                mechanic.on_object_tick(oracle_source, dt_ms)
            result = step_runtime_periodic_spawners_(
                runtime,
                catalog,
                state,
                dt_ms=dt_ms,
                facing_x_units=facing_x,
                facing_y_units=facing_y,
            )
            assert result.committed.tolist() == [True]
            valid = result.allocation.valid[0]
            child_slots = result.allocation.slots[0, valid]
            assert not runtime.status.freeze_expiry_time[0, child_slots].any()
            assert not result.child_target_distance_discount_sq_units[0, valid].any()
            assert _tensor_events(runtime, tensor_event_start) == _oracle_events(
                capture.events[oracle_event_start:], runtime
            )
            oracle_event_start = len(capture.events)

    assert _represented(runtime) == _oracle(oracle)
    assert runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id
    assert torch.equal(runtime.battle.rng.words, rng_before[0])
    assert torch.equal(runtime.battle.rng.index, rng_before[1])
    for child_id, oracle_child in oracle.entities.items():
        if child_id == entity.id:
            continue
        slot = int(torch.nonzero(runtime.battle.entity_id[0] == child_id).item())
        assert runtime.battle.entity_deploy_delay[0, slot].item() == (
            oracle_child.deploy_delay_remaining
        )


def test_simultaneous_sources_allocate_children_in_source_id_order() -> None:
    battle, first = _battle("Witch", x=7.0)
    stats = battle.card_loader.get_card("NightWitch")
    assert stats is not None
    second = battle._spawn_entity(Troop, Position(11.0, 10.0), 0, stats)
    second.deploy_delay_remaining = 0.0
    second.placement_pending = False
    oracle = copy.deepcopy(battle)
    for entity_id in sorted(oracle.entities):
        _mechanic(oracle.entities[entity_id]).on_object_tick(
            oracle.entities[entity_id], 1_000
        )
    runtime, state, catalog = _runtime(battle, device="cpu")
    facing_x = torch.zeros_like(runtime.battle.entity_x_units)
    facing_y = torch.ones_like(runtime.battle.entity_y_units)

    result = step_runtime_periodic_spawners_(
        runtime,
        catalog,
        state,
        dt_ms=1_000,
        facing_x_units=facing_x,
        facing_y_units=facing_y,
    )

    assert result.committed.tolist() == [True]
    assert result.child_source_id[0, :2].tolist() == [first.id, second.id]
    assert result.allocation.entity_ids[0, :2].tolist() == [3, 4]


@pytest.mark.parametrize(
    "device",
    (
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ),
)
def test_forced_multi_source_partial_waves_preserve_ids_events_and_rng(
    device: str,
) -> None:
    battle, first = _battle("Witch", x=7.0)
    stats = battle.card_loader.get_card("Witch")
    assert stats is not None
    second = battle._spawn_entity(Troop, Position(11.0, 10.0), 0, stats)
    second.deploy_delay_remaining = 0.0
    second.placement_pending = False
    second._spawn_hook_pending = False
    second._spawn_hook_fired = True
    second._facing_x_units = -300
    second._facing_y_units = 400
    oracle = copy.deepcopy(battle)
    runtime, state, catalog = _runtime(battle, device=device)
    facing_x = torch.zeros_like(runtime.battle.entity_x_units)
    facing_y = torch.zeros_like(runtime.battle.entity_y_units)
    facing_x[0, :2] = torch.tensor([300, -300], device=runtime.device)
    facing_y[0, :2] = 400
    rng_before = runtime.battle.rng.python_state(0)

    with PythonOracleEventCapture(oracle) as capture:
        with capture._scope(phase=TickPhase.OBJECTS):
            for entity_id in (first.id, second.id):
                _mechanic(oracle.entities[entity_id]).on_object_tick(
                    oracle.entities[entity_id], 1_100
                )
        result = step_runtime_periodic_spawners_(
            runtime,
            catalog,
            state,
            dt_ms=1_100,
            facing_x_units=facing_x,
            facing_y_units=facing_y,
        )

    assert result.committed.tolist() == [True]
    assert result.child_source_id[0, :6].tolist() == [1, 1, 1, 2, 2, 2]
    assert result.child_formation_index[0, :6].tolist() == [0, 1, 2, 0, 1, 2]
    assert result.allocation.entity_ids[0, :6].tolist() == [3, 4, 5, 6, 7, 8]
    assert _tensor_events(runtime) == _oracle_events(capture.events, runtime)
    assert _represented(runtime) == _oracle(oracle)
    assert runtime.battle.rng.python_state(0) == rng_before == oracle.rng.getstate()
    assert runtime.events.opcode[0, :6].tolist() == [RuntimeEventOpcode.SPAWN] * 6
    assert runtime.events.source_id[0, :6].tolist() == [0] * 6


@pytest.mark.parametrize(
    "device",
    (
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ),
)
def test_event_capacity_failure_rolls_back_runtime_and_clocks(device: str) -> None:
    battle, _ = _battle("Witch")
    runtime, state, catalog = _runtime(battle, device=device, event_capacity=1)
    runtime.events.count[0] = 1
    before_ids = runtime.battle.entity_id.clone()
    before_next = runtime.entity_pool.next_entity_id.clone()
    before_events = {
        descriptor.name: getattr(runtime.events, descriptor.name).clone()
        for descriptor in fields(runtime.events)
    }
    before_state = state.clone()
    before_rng = runtime.battle.rng.python_state(0)

    result = step_runtime_periodic_spawners_(
        runtime,
        catalog,
        state,
        dt_ms=1_000,
    )

    assert result.committed.tolist() == [False]
    assert result.reason.tolist() == [PeriodicSpawnerReason.EVENT_CAPACITY]
    assert torch.equal(runtime.battle.entity_id, before_ids)
    assert torch.equal(runtime.entity_pool.next_entity_id, before_next)
    for name, expected in before_events.items():
        assert torch.equal(getattr(runtime.events, name), expected), name
    for name in vars(before_state):
        assert torch.equal(getattr(state, name), getattr(before_state, name)), name
    assert runtime.battle.rng.python_state(0) == before_rng


def test_source_death_resets_retained_clocks_and_emits_nothing() -> None:
    battle, source = _battle("Witch")
    runtime, state, catalog = _runtime(battle, device="cpu")
    step_runtime_periodic_spawners_(runtime, catalog, state, dt_ms=500)
    slot = int(torch.nonzero(runtime.battle.entity_id[0] == source.id).item())
    runtime.battle.entity_active[0, slot] = False

    result = step_runtime_periodic_spawners_(runtime, catalog, state, dt_ms=1_000)

    assert result.committed.tolist() == [True]
    assert result.schedule.batch_index.numel() == 0
    assert state.source_entity_id[0, slot].item() == 0
    assert state.operation_row[0, slot].item() == -1
    assert state.time_since_spawn_ms[0, slot].item() == 0.0


@pytest.mark.parametrize(
    "device",
    [
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ],
)
def test_deployment_pending_clock_starts_on_zero_crossing_frame(device: str) -> None:
    battle, source = _battle("NightWitch")
    source.deploy_delay_remaining = 1.0
    source.placement_pending = True
    oracle = copy.deepcopy(battle)
    oracle_source = oracle.entities[source.id]
    assert isinstance(oracle_source, (Troop, Building))
    oracle_mechanic = _mechanic(oracle_source)
    runtime, state, catalog = _runtime(battle, device=device)
    source_slot = int(
        torch.nonzero(runtime.battle.entity_id[0] == source.id, as_tuple=False)[0, 0]
    )

    for tick in range(20):
        oracle_source.tick_character_object_phase(0.05)
        remaining = torch.clamp(
            runtime.battle.entity_deploy_delay - 0.05,
            min=0.0,
        )
        deploying = runtime.battle.entity_deploy_delay > 0.0
        runtime.battle.entity_deploy_delay.copy_(
            torch.where(deploying, remaining, runtime.battle.entity_deploy_delay)
        )
        completed = deploying & (remaining <= 1e-9)
        runtime.battle.entity_placement_pending &= ~completed
        runtime.battle.entity_spawn_hook_pending &= ~completed
        result = step_runtime_periodic_spawners_(
            runtime,
            catalog,
            state,
            dt_ms=50,
        )

        assert result.committed.tolist() == [True]
        assert not result.allocation.valid.any()
        assert state.time_since_spawn_ms[0, source_slot].item() == (
            oracle_mechanic.time_since_spawn_ms
        )
        if tick < 19:
            assert state.source_entity_id[0, source_slot].item() == 0

    assert state.source_entity_id[0, source_slot].item() == source.id
    assert state.time_since_spawn_ms[0, source_slot].item() == 50.0
    assert runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id


def test_state_clone_fork_and_reset_are_independent() -> None:
    battle, _ = _battle("NightWitch")
    runtime, state, catalog = _runtime(battle, device="cpu")
    step_runtime_periodic_spawners_(runtime, catalog, state, dt_ms=500)
    cloned = state.clone()
    forked = state.fork([0, 0])
    assert cloned.time_since_spawn_ms.data_ptr() != state.time_since_spawn_ms.data_ptr()
    assert forked.time_since_spawn_ms.shape[0] == 2
    mask = torch.ones_like(cloned.source_entity_id, dtype=torch.bool)
    cloned.reset_(mask)
    assert state.time_since_spawn_ms.any()
    assert not cloned.time_since_spawn_ms.any()


@pytest.mark.parametrize(
    "device",
    [
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ],
)
def test_per_battle_dt_broadcasts_across_non_square_entity_plane(
    device: str,
) -> None:
    battles = [_battle(root)[0] for root in ROOTS]
    catalog = _catalog(device)
    runtime = TensorBattleRuntime.from_battles(
        battles,
        device=device,
        max_entities=7,
        event_capacity=64,
        catalog=catalog.cards,
    )
    catalog.prepare_runtime(runtime)
    state = TensorPeriodicSpawnerRuntimeState.zeros(runtime)
    dt_ms = torch.tensor((50.0, 75.0, 125.0), device=device)

    result = step_runtime_periodic_spawners_(
        runtime,
        catalog,
        state,
        dt_ms=dt_ms,
    )

    assert result.committed.tolist() == [True, True, True]
    source_slots = runtime.entity_pool.id_order(runtime.entity_pool.active).slots[:, 0]
    rows = torch.arange(3, dtype=torch.int64, device=runtime.device)
    assert torch.equal(
        state.time_since_spawn_ms[rows, source_slots],
        dt_ms.to(torch.float64),
    )
