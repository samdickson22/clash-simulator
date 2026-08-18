from __future__ import annotations

import copy
from typing import cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity
from clasher.mechanics.shared.spawner import PeriodicSpawner
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace


def _battle(root: str) -> tuple[BattleState, Entity, PeriodicSpawner]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(root)
    assert stats is not None
    # Isolate the character-owned object phase from troop movement and combat;
    # Building and Troop share the authoritative object-tick implementation.
    source = battle._spawn_entity(Building, Position(9.0, 10.0), 0, stats)
    source.deploy_delay_remaining = 0.0
    source.placement_pending = False
    source._spawn_hook_pending = False
    source._spawn_hook_fired = True
    source._facing_x_units = 300
    source._facing_y_units = 400
    mechanic = next(
        cast(PeriodicSpawner, candidate)
        for candidate in source.mechanics
        if isinstance(candidate, PeriodicSpawner)
    )
    first = mechanic.first_spawn_delay_ms or mechanic.spawn_interval_ms
    mechanic.time_since_spawn_ms = float(first - 50)
    return battle, source, mechanic


def _represented(
    engine: TensorResidentEngine,
) -> list[tuple[int, str, int, int, float]]:
    core = engine.runtime.battle
    return sorted(
        (
            int(core.entity_id[0, slot]),
            core.card_names[int(core.entity_card[0, slot])],
            int(core.entity_x_units[0, slot]),
            int(core.entity_y_units[0, slot]),
            float(core.entity_deploy_delay[0, slot]),
        )
        for slot in range(engine.runtime.max_entities)
        if bool(engine.runtime.entity_pool.active[0, slot])
    )


def _oracle_represented(battle: BattleState) -> list[tuple[int, str, int, int, float]]:
    return [
        (
            entity_id,
            str(entity.card_stats.name),
            round(entity.position.x * 1_000),
            round(entity.position.y * 1_000),
            float(entity.deploy_delay_remaining),
        )
        for entity_id, entity in sorted(battle.entities.items())
    ]


@pytest.mark.parametrize("root", ("NightWitch", "Tombstone", "Witch"))
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
def test_engine_materializes_first_periodic_child_exactly(
    root: str,
    device: str,
) -> None:
    battle, _, _ = _battle(root)
    oracle = copy.deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle], device=device, max_entities=32, event_capacity=128
    )

    ids = set(oracle.entities)
    oracle._run_object_phase(oracle.dt, ids, ids)
    oracle._cleanup_dead_entities()
    result = engine.step()

    assert result.committed.tolist() == [True]
    assert result.periodic_spawner is not None
    assert result.periodic_spawner.committed.tolist() == [True]
    assert _represented(engine) == _oracle_represented(oracle)
    assert engine.runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id


def test_periodic_capacity_failure_rolls_back_whole_engine_row() -> None:
    battle, _, _ = _battle("Witch")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=1, event_capacity=128
    )
    before_time = engine.runtime.battle.time.clone()
    before_ids = engine.runtime.battle.entity_id.clone()
    before_periodic = engine.periodic_state.clone()

    result = engine.step()

    assert result.committed.tolist() == [False]
    assert torch.equal(engine.runtime.battle.time, before_time)
    assert torch.equal(engine.runtime.battle.entity_id, before_ids)
    for name in vars(before_periodic):
        assert torch.equal(
            getattr(engine.periodic_state, name), getattr(before_periodic, name)
        )


def test_workspace_owns_and_refreshes_periodic_state() -> None:
    battle, _, _ = _battle("Tombstone")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, event_capacity=128
    )
    workspace = TensorResidentWorkspace(engine)
    assert workspace.scratch.periodic_state.source_entity_id.data_ptr() != (
        engine.periodic_state.source_entity_id.data_ptr()
    )

    result = workspace.step()

    assert result.committed.tolist() == [True]
    assert torch.equal(
        workspace.scratch.periodic_state.time_since_spawn_ms,
        engine.periodic_state.time_since_spawn_ms,
    )
