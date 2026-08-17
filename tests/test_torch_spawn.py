import copy
import json
from collections import deque
from dataclasses import replace
from pathlib import Path
from types import MethodType
from typing import Any

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.mechanics.shared.death_effects import DeathSpawn
from clasher.mechanics.shared.spawner import PeriodicSpawner
from clasher.torch_sim.catalog import MECHANIC_OPCODE
from clasher.torch_sim.spawn import (
    TensorDeathSpawnSources,
    TensorPeriodicSpawnerState,
    TensorSpawnCatalog,
    plan_death_spawns,
    step_periodic_spawners,
)


def _enabled_names(loader: CardDataLoader) -> set[str]:
    definitions = loader.load_card_definitions()
    decks = json.loads(Path("decks.json").read_text())["decks"]
    return {
        resolve_card_name(card, definitions) for deck in decks for card in deck["cards"]
    }


class _SpawnerEntity:
    def __init__(self) -> None:
        self.battle_state = type("BattleStub", (), {"debug_logs": False})()
        self.stunned = False
        self.spawn_rate = 1.0

    def is_stunned(self) -> bool:
        return self.stunned

    def get_spawn_rate_multiplier(self) -> float:
        return self.spawn_rate


def _oracle_spawners(
    loader: CardDataLoader,
    catalog: TensorSpawnCatalog,
    rows: torch.Tensor | None = None,
) -> tuple[PeriodicSpawner, ...]:
    definitions = loader.load_card_definitions()
    mechanics: list[PeriodicSpawner] = []
    selected_rows = catalog.periodic_rows() if rows is None else rows
    for row in selected_rows.tolist():
        source_name = catalog.source_names[row]
        slot = int(catalog.source_mechanic_slot[row].item())
        mechanic = definitions[source_name].mechanics[slot]
        assert isinstance(mechanic, PeriodicSpawner)
        mechanics.append(copy.deepcopy(mechanic))
    return tuple(mechanics)


def _death_sources(batch_size: int, source_count: int) -> TensorDeathSpawnSources:
    shape = (batch_size, source_count)
    ordinal = torch.arange(batch_size * source_count).reshape(shape)
    return TensorDeathSpawnSources(
        entity_id=100 + ordinal,
        player=(ordinal % 2).to(torch.int8),
        x_units=(9_000 + ordinal * 10).to(torch.int32),
        y_units=(10_000 + ordinal * 20).to(torch.int32),
        facing_x_units=(100 + ordinal).to(torch.int32),
        facing_y_units=(-200 - ordinal).to(torch.int32),
        freeze_expiry_time=12.5 + ordinal.to(torch.float64),
    )


def test_spawn_catalog_inventories_transitive_enabled_payloads() -> None:
    loader = CardDataLoader()
    catalog = TensorSpawnCatalog.compile(loader, _enabled_names(loader))

    assert catalog.operation_count == 12
    assert catalog.periodic_rows().numel() == 3
    assert catalog.death_rows().numel() == 9
    assert {catalog.root_names[row] for row in catalog.periodic_rows().tolist()} == {
        "NightWitch",
        "Tombstone",
        "Witch",
    }

    nested_rows = catalog.depth.nonzero(as_tuple=False)[:, 0].tolist()
    assert len(nested_rows) == 1
    nested_row = nested_rows[0]
    assert catalog.root_names[nested_row] == "SkeletonBarrel"
    assert catalog.source_names[nested_row] == "SkeletonContainerNew"
    assert catalog.unit_names[nested_row] == "Skeleton"
    assert int(catalog.count[nested_row].item()) == 7
    assert (
        int(catalog.mechanic_opcode[nested_row].item()) == MECHANIC_OPCODE["DeathSpawn"]
    )
    assert int(catalog.parent_row[nested_row].item()) >= 0

    explosive_rows = catalog.timed_explosive.nonzero(as_tuple=False)[:, 0].tolist()
    assert {catalog.root_names[row] for row in explosive_rows} == {
        "Balloon",
        "BombTower",
        "SkeletonBarrel",
    }


def test_periodic_spawner_kernel_matches_oracle_clocks_and_events() -> None:
    loader = CardDataLoader()
    catalog = TensorSpawnCatalog.compile(loader, _enabled_names(loader))
    oracle = _oracle_spawners(loader, catalog)
    state = TensorPeriodicSpawnerState.zeros(1, len(oracle))
    entities = tuple(_SpawnerEntity() for _ in oracle)
    oracle_events: list[list[tuple[int, int]]] = [[] for _ in oracle]
    ordered_oracle_events: list[tuple[int, int, int]] = []

    for operation_index, mechanic in enumerate(oracle):

        def record(
            _self: PeriodicSpawner,
            _entity: Any,
            *,
            count: int,
            start_index: int,
            wave_size: int,
            operation_index: int = operation_index,
        ) -> None:
            oracle_events[operation_index].extend(
                (index, wave_size) for index in range(start_index, start_index + count)
            )
            ordered_oracle_events.extend(
                (operation_index, index, wave_size)
                for index in range(start_index, start_index + count)
            )

        mechanic._spawn_units = MethodType(record, mechanic)

    # This sequence covers exact first-wave boundaries, staggered members,
    # ordinary inter-wave accumulation, a stun pause, and fractional Rage time.
    timeline = (
        (50, (False, False, False), (1.0, 1.0, 1.0)),
        (900, (False, False, False), (1.0, 1.0, 1.0)),
        (50, (False, False, False), (1.0, 1.0, 1.0)),
        (50, (False, False, False), (1.0, 1.0, 1.0)),
        (3250, (False, True, False), (1.3, 1.0, 1.3)),
        (500, (False, False, False), (1.3, 1.0, 1.3)),
        (7200, (False, False, False), (1.0, 1.3, 1.0)),
    )
    for dt_ms, stunned, rates in timeline:
        before = [len(events) for events in oracle_events]
        ordered_before = len(ordered_oracle_events)
        for mechanic, entity, is_stunned, rate in zip(oracle, entities, stunned, rates):
            entity.stunned = is_stunned
            entity.spawn_rate = rate
            mechanic.on_object_tick(entity, dt_ms)

        events = step_periodic_spawners(
            catalog,
            state,
            dt_ms,
            active=torch.tensor([[not value for value in stunned]]),
            spawn_rate=torch.tensor([rates], dtype=torch.float64),
        )
        tensor_events = [[] for _ in oracle]
        for operation_index, formation_index, wave_size in zip(
            events.operation_index.tolist(),
            events.formation_index.tolist(),
            events.wave_size.tolist(),
        ):
            tensor_events[operation_index].append((formation_index, wave_size))
        assert tensor_events == [
            values[start:] for values, start in zip(oracle_events, before)
        ]
        assert (
            list(
                zip(
                    events.operation_index.tolist(),
                    events.formation_index.tolist(),
                    events.wave_size.tolist(),
                )
            )
            == ordered_oracle_events[ordered_before:]
        )

        for index, mechanic in enumerate(oracle):
            assert state.time_since_spawn_ms[0, index].item() == (
                mechanic.time_since_spawn_ms
            )
            assert state.spawns_created[0, index].item() == mechanic.spawns_created
            assert state.pending_units[0, index].item() == mechanic.pending_units
            assert state.time_since_unit_spawn_ms[0, index].item() == (
                mechanic.time_since_unit_spawn_ms
            )
            assert state.current_wave_spawned[0, index].item() == (
                mechanic.current_wave_spawned
            )


def test_periodic_spawner_coarse_budget_preserves_global_oracle_order() -> None:
    loader = CardDataLoader()
    catalog = TensorSpawnCatalog.compile(loader, _enabled_names(loader))
    operation_rows = catalog.periodic_rows().flip(0)
    oracle = tuple(reversed(_oracle_spawners(loader, catalog)))
    state = TensorPeriodicSpawnerState.zeros(1, len(oracle))
    entity = _SpawnerEntity()
    expected: list[tuple[int, int, int]] = []

    for operation_index, mechanic in enumerate(oracle):

        def record(
            _self: PeriodicSpawner,
            _entity: Any,
            *,
            count: int,
            start_index: int,
            wave_size: int,
            operation_index: int = operation_index,
        ) -> None:
            expected.extend(
                (operation_index, index, wave_size)
                for index in range(start_index, start_index + count)
            )

        mechanic._spawn_units = MethodType(record, mechanic)
        # Python's entity-ID component pass drains this source's full budget
        # before visiting the next source.
        mechanic.on_object_tick(entity, 15_000)

    events = step_periodic_spawners(
        catalog,
        state,
        15_000.0,
        operation_rows=operation_rows,
    )
    actual = list(
        zip(
            events.operation_index.tolist(),
            events.formation_index.tolist(),
            events.wave_size.tolist(),
        )
    )

    assert actual == expected
    assert len(actual) > len(oracle)


def test_periodic_spawner_kernel_batches_independent_states() -> None:
    loader = CardDataLoader()
    catalog = TensorSpawnCatalog.compile(loader, _enabled_names(loader))
    state = TensorPeriodicSpawnerState.zeros(2, 3)
    state.time_since_spawn_ms[1] = torch.tensor((975.0, 3475.0, 975.0))

    events = step_periodic_spawners(
        catalog,
        state,
        50,
        active=torch.tensor(((True, True, True), (True, True, True))),
        spawn_rate=torch.tensor(((1.0, 1.0, 1.0), (0.5, 0.5, 0.5))),
    )

    assert events.batch_index.tolist() == [1, 1, 1]
    assert events.operation_index.tolist() == [0, 1, 2]
    assert events.formation_index.tolist() == [0, 0, 0]
    assert events.wave_size.tolist() == [2, 2, 4]
    assert state.time_since_spawn_ms[0].tolist() == [50.0, 50.0, 50.0]


def test_periodic_spawner_kernel_matches_heterogeneous_batch_layouts() -> None:
    loader = CardDataLoader()
    catalog = TensorSpawnCatalog.compile(loader, _enabled_names(loader))
    periodic_rows = catalog.periodic_rows()
    operation_rows = torch.stack(
        (
            periodic_rows,
            periodic_rows[torch.tensor((2, 0, 0))],
        )
    )
    state = TensorPeriodicSpawnerState.zeros(2, 3)
    expected: list[list[tuple[int, int, int]]] = [[], []]
    oracle_states: list[tuple[PeriodicSpawner, ...]] = []

    for batch_index in range(2):
        oracle = _oracle_spawners(loader, catalog, operation_rows[batch_index])
        oracle_states.append(oracle)
        entity = _SpawnerEntity()
        for source_column, mechanic in enumerate(oracle):

            def record(
                _self: PeriodicSpawner,
                _entity: Any,
                *,
                count: int,
                start_index: int,
                wave_size: int,
                batch_index: int = batch_index,
                source_column: int = source_column,
            ) -> None:
                expected[batch_index].extend(
                    (source_column, index, wave_size)
                    for index in range(start_index, start_index + count)
                )

            mechanic._spawn_units = MethodType(record, mechanic)
            mechanic.on_object_tick(entity, 15_000)

    events = step_periodic_spawners(
        catalog,
        state,
        15_000.0,
        operation_rows=operation_rows,
    )
    actual: list[list[tuple[int, int, int]]] = [[], []]
    for batch, source, row, formation, wave in zip(
        events.batch_index.tolist(),
        events.source_column.tolist(),
        events.catalog_row.tolist(),
        events.formation_index.tolist(),
        events.wave_size.tolist(),
    ):
        assert row == int(operation_rows[batch, source].item())
        actual[batch].append((source, formation, wave))

    assert actual == expected
    for batch_index, oracle in enumerate(oracle_states):
        assert state.spawns_created[batch_index].tolist() == [
            mechanic.spawns_created for mechanic in oracle
        ]
        assert state.pending_units[batch_index].tolist() == [
            mechanic.pending_units for mechanic in oracle
        ]
        assert state.time_since_spawn_ms[batch_index].tolist() == [
            mechanic.time_since_spawn_ms for mechanic in oracle
        ]
        assert state.time_since_unit_spawn_ms[batch_index].tolist() == [
            mechanic.time_since_unit_spawn_ms for mechanic in oracle
        ]
        assert state.current_wave_spawned[batch_index].tolist() == [
            mechanic.current_wave_spawned for mechanic in oracle
        ]


def test_death_spawn_planner_preserves_serialized_child_order() -> None:
    loader = CardDataLoader()
    catalog = TensorSpawnCatalog.compile(loader, _enabled_names(loader))
    death_rows = catalog.death_rows()
    dead = torch.zeros((2, death_rows.numel()), dtype=torch.bool)
    dead[0, 0] = True
    dead[0, -1] = True
    dead[1, 3] = True

    sources = _death_sources(2, death_rows.numel())
    events = plan_death_spawns(
        catalog,
        dead,
        operation_rows=death_rows,
        sources=sources,
    )

    expected_counts = catalog.count[death_rows]
    assert events.batch_index.tolist() == (
        [0] * int(expected_counts[0].item())
        + [0] * int(expected_counts[-1].item())
        + [1] * int(expected_counts[3].item())
    )
    assert events.source_column.tolist() == (
        [0] * int(expected_counts[0].item())
        + [death_rows.numel() - 1] * int(expected_counts[-1].item())
        + [3] * int(expected_counts[3].item())
    )
    offset = 0
    for count in (
        int(expected_counts[0].item()),
        int(expected_counts[-1].item()),
        int(expected_counts[3].item()),
    ):
        assert events.formation_index[offset : offset + count].tolist() == list(
            range(count)
        )
        offset += count


def test_death_spawn_planner_keeps_duplicate_sources_and_context_distinct() -> None:
    loader = CardDataLoader()
    catalog = TensorSpawnCatalog.compile(loader, _enabled_names(loader))
    death_rows = catalog.death_rows()
    repeated_row = death_rows[3]
    operation_rows = torch.stack((repeated_row, repeated_row, death_rows[0]))
    dead = torch.ones((1, 3), dtype=torch.bool)
    sources = _death_sources(1, 3)

    events = plan_death_spawns(
        catalog,
        dead,
        operation_rows=operation_rows,
        sources=sources,
    )

    repeated_count = int(catalog.count[repeated_row].item())
    final_count = int(catalog.count[death_rows[0]].item())
    assert events.source_column.tolist() == (
        [0] * repeated_count + [1] * repeated_count + [2] * final_count
    )
    assert events.catalog_row.tolist() == (
        [int(repeated_row.item())] * (2 * repeated_count)
        + [int(death_rows[0].item())] * final_count
    )
    assert events.source_entity_id.tolist() == (
        [100] * repeated_count + [101] * repeated_count + [102] * final_count
    )
    assert events.source_player.tolist() == (
        [0] * repeated_count + [1] * repeated_count + [0] * final_count
    )
    assert events.source_x_units.tolist() == (
        [9_000] * repeated_count + [9_010] * repeated_count + [9_020] * final_count
    )
    assert events.source_facing_y_units.tolist() == (
        [-200] * repeated_count + [-201] * repeated_count + [-202] * final_count
    )
    assert events.source_freeze_expiry_time.tolist() == (
        [12.5] * repeated_count + [13.5] * repeated_count + [14.5] * final_count
    )


def test_death_spawn_zero_count_is_preserved_and_emits_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = CardDataLoader()
    definitions = dict(loader.load_card_definitions())
    definitions["ZeroDeathSpawn"] = replace(
        definitions["Knight"],
        name="ZeroDeathSpawn",
        mechanics=(DeathSpawn(unit_name="Skeleton", count=0),),
    )
    monkeypatch.setattr(loader, "load_card_definitions", lambda: definitions)
    catalog = TensorSpawnCatalog.compile(loader, ["ZeroDeathSpawn"])

    assert catalog.count.tolist() == [0]
    events = plan_death_spawns(
        catalog,
        torch.ones((1, 1), dtype=torch.bool),
        operation_rows=torch.tensor([0]),
        sources=_death_sources(1, 1),
    )

    assert events.batch_index.numel() == 0
    assert events.source_entity_id.numel() == 0


def test_death_spawn_catalog_counts_match_oracle_allocations() -> None:
    loader = CardDataLoader()
    catalog = TensorSpawnCatalog.compile(loader, _enabled_names(loader))
    direct_death_rows = [
        row
        for row in catalog.death_rows().tolist()
        if int(catalog.depth[row].item()) == 0
    ]

    for row in direct_death_rows:
        battle = BattleState()
        root_name = catalog.root_names[row]
        player = battle.players[0]
        player.elixir = 10.0
        player.hand = [root_name]
        player.deck = [root_name]
        player.cycle_queue = deque()
        ids_before_deploy = set(battle.entities)

        assert battle.deploy_card(0, root_name, Position(9.0, 10.0))
        deployed = [
            entity
            for entity_id, entity in battle.entities.items()
            if entity_id not in ids_before_deploy
        ]
        assert len(deployed) == 1
        parent = deployed[0]
        parent.deploy_delay_remaining = 0.0
        parent.placement_pending = False
        parent.on_spawn()
        ids_before_death = set(battle.entities)

        parent.take_damage(parent.hitpoints)

        spawned_ids = set(battle.entities) - ids_before_death
        assert len(spawned_ids) == int(catalog.count[row].item()), root_name
