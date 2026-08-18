from __future__ import annotations

import copy

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
from clasher.torch_sim.resident_engine import (
    ResidentUnsupportedReason,
    TensorResidentEngine,
)
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace

ROOT_MECHANICS = {
    "Balloon": (True, ("DeathSpawn",)),
    "BattleRam": (False, ("DeathSpawn", "BattleRamCharge")),
    "BombTower": (True, ("DeathSpawn",)),
    "Golem": (False, ("DeathDamage", "DeathSpawn")),
    "LavaHound": (True, ("DeathSpawn",)),
    "NightWitch": (True, ("DeathSpawn", "PeriodicSpawner")),
    "SkeletonBarrel": (False, ("DeathSpawn", "BattleRamCharge")),
    "Tombstone": (True, ("DeathSpawn", "PeriodicSpawner")),
}


def _battle(root: str) -> tuple[BattleState, Entity]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(root)
    assert stats is not None
    entity_type = Building if str(stats.card_type).casefold() == "building" else Troop
    parent = battle._spawn_entity(entity_type, Position(9.0, 10.0), 0, stats)
    parent.deploy_delay_remaining = 0.0
    parent.placement_pending = False
    parent._spawn_hook_pending = False
    parent._spawn_hook_fired = True
    parent._facing_x_units = 300
    parent._facing_y_units = 400
    return battle, parent


def _represented(
    engine: TensorResidentEngine,
) -> list[tuple[int, str, int, int, float]]:
    rows = []
    core = engine.runtime.battle
    for slot in range(engine.runtime.max_entities):
        if not engine.runtime.entity_pool.active[0, slot]:
            continue
        rows.append(
            (
                int(core.entity_id[0, slot]),
                core.card_names[int(core.entity_card[0, slot])],
                int(core.entity_x_units[0, slot]),
                int(core.entity_y_units[0, slot]),
                float(core.entity_hp[0, slot]),
            )
        )
    return sorted(rows)


def _oracle_after_death(
    battle: BattleState,
    parent_id: int,
) -> list[tuple[int, str, int, int, float]]:
    oracle = copy.deepcopy(battle)
    parent = oracle.entities[parent_id]
    parent.take_damage(parent.hitpoints)
    oracle._cleanup_dead_entities()
    return [
        (
            entity_id,
            str(entity.card_stats.name),
            round(entity.position.x * 1_000),
            round(entity.position.y * 1_000),
            float(entity.hitpoints),
        )
        for entity_id, entity in sorted(oracle.entities.items())
    ]


@pytest.mark.parametrize("root", tuple(ROOT_MECHANICS))
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
def test_engine_terminal_admission_matches_complete_mechanic_sets(
    root: str,
    device: str,
) -> None:
    battle, parent = _battle(root)
    expected = _oracle_after_death(battle, parent.id)
    parent.hitpoints = 0.0
    parent.is_alive = False
    engine = TensorResidentEngine.from_battles(
        [battle], device=device, max_entities=32, event_capacity=256
    )
    admitted, _ = ROOT_MECHANICS[root]

    preflight = engine.preflight()
    assert preflight.supported.tolist() == [admitted]
    if not admitted:
        assert preflight.reason_code.tolist() == [
            ResidentUnsupportedReason.ACTIVE_MECHANIC
        ]
        return

    result = engine.step()

    assert result.committed.tolist() == [True]
    assert result.terminal is not None
    assert result.terminal.committed.tolist() == [True]
    assert _represented(engine) == expected
    if root in {"Balloon", "BombTower"}:
        active = engine.terminal_pipeline.state.objects.allocated
        assert engine.terminal_pipeline.state.objects.age_ms[active].tolist() == [0]


def test_workspace_refresh_and_commit_own_terminal_state_independently() -> None:
    battle, parent = _battle("Balloon")
    parent.hitpoints = 0.0
    parent.is_alive = False
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, event_capacity=128
    )
    workspace = TensorResidentWorkspace(engine)
    front_ptr = engine.terminal_pipeline.state.objects.object_id.data_ptr()
    scratch_ptr = workspace.scratch.terminal_pipeline.state.objects.object_id.data_ptr()
    assert front_ptr != scratch_ptr

    first = workspace.step()
    assert first.committed.tolist() == [True]
    assert engine.terminal_pipeline.state.objects.allocated.sum().item() == 1
    assert workspace.scratch.terminal_pipeline.state.objects.allocated.sum().item() == 1
    engine.runtime.events.clear()
    second = workspace.step()
    assert second.committed.tolist() == [True]
    assert engine.terminal_pipeline.state.objects.age_ms[0, 0].item() == 50
