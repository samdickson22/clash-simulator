from __future__ import annotations

import copy
from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import AreaEffect, BuffAreaEffect, DeathAreaEffectContainer, Troop
from clasher.torch_sim.resident_death_payloads import (
    DeathPayloadReason,
    TensorDeathPayloadState,
    step_death_payloads_,
)
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    yield device


def _spawn(battle: BattleState, name: str, player: int, position: Position) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    battle._spawn_unit_at_position(
        position, player, stats, deploy_delay_override=0.0, snap_to_valid=False
    )
    entity = battle.entities[battle.next_entity_id - 1]
    assert isinstance(entity, Troop)
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.speed = 0.0
    return entity


def _battle(source_name: str) -> tuple[BattleState, Troop, list[Troop]]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn(battle, source_name, 0, Position(9.0, 10.0))
    targets = [
        _spawn(battle, "Knight", 1, Position(8.0, 10.0)),
        _spawn(battle, "Knight", 1, Position(10.0, 10.0)),
    ]
    source.is_alive = False
    source.hitpoints = 0
    return battle, source, targets


def _slot(runtime: TensorBattleRuntime, entity_id: int, row: int = 0) -> int:
    found = torch.where(runtime.battle.entity_id[row] == entity_id)[0]
    assert found.numel() == 1
    return int(found[0].item())


def _run_scalar_payloads(battle: BattleState, source_id: int) -> None:
    source = battle.entities[source_id]
    for mechanic in source.mechanics:
        if type(mechanic).__name__ in {"DeathDamage", "DeathAreaEffect"}:
            mechanic.on_death(source)


def test_golem_damage_shield_knockback_and_terminal_handoff_match_scalar(
    tensor_device: str,
) -> None:
    battle, source, targets = _battle("Golem")
    guard = _spawn(battle, "Guards", 1, Position(9.0, 11.0))
    oracle = battle.clone()
    _run_scalar_payloads(oracle, source.id)
    runtime = TensorBattleRuntime.from_battles(
        [battle], device=tensor_device, max_entities=8, event_capacity=32
    )
    state = TensorDeathPayloadState.from_battles(runtime, [battle])
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, source.id)] = True

    result = step_death_payloads_(runtime, state, dead)

    assert result.committed.tolist() == [True]
    assert result.terminal_dead[0, _slot(runtime, source.id)].item()
    for target in [*targets, guard]:
        slot = _slot(runtime, target.id)
        assert (
            runtime.battle.entity_hp[0, slot].item()
            == oracle.entities[target.id].hitpoints
        )
    oracle_guard_shield = next(
        m for m in oracle.entities[guard.id].mechanics if type(m).__name__ == "Shield"
    )
    assert (
        state.shield_current[0, _slot(runtime, guard.id)].item()
        == vars(oracle_guard_shield)["current_shield"]
    )
    assert result.knockback.valid.any().item()
    count = int(runtime.events.count[0].item())
    assert runtime.events.opcode[0, :count].tolist()[0] == RuntimeEventOpcode.DAMAGE
    assert (
        runtime.events.phase[0, :count].tolist()
        == [TickPhase.CLEANUP_AND_SPAWNS] * count
    )


@pytest.mark.parametrize("source_name", ("IceGolem", "Lumberjack"))
def test_death_area_descriptor_matches_scalar_materialized_area(
    source_name: str,
) -> None:
    battle, source, targets = _battle(source_name)
    oracle = battle.clone()
    _run_scalar_payloads(oracle, source.id)
    scalar_area = next(
        entity
        for entity in oracle.entities.values()
        if isinstance(entity, (AreaEffect, BuffAreaEffect, DeathAreaEffectContainer))
    )
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=32
    )
    state = TensorDeathPayloadState.from_battles(runtime, [battle])
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, source.id)] = True

    result = step_death_payloads_(runtime, state, dead)

    assert result.committed.tolist() == [True]
    area_slot = int(torch.where(result.areas.valid[0])[0][0].item())
    assert result.areas.object_id[0, area_slot].item() == scalar_area.id
    assert result.areas.source_id[0, area_slot].item() == source.id
    if isinstance(scalar_area, DeathAreaEffectContainer):
        assert result.areas.activation_delay_ms[0, area_slot].item() == round(
            scalar_area.activation_delay * 1_000
        )
        assert result.areas.radius_units[0, area_slot].item() == int(
            scalar_area.area_data["radius"]
        )
    else:
        assert result.areas.radius_units[0, area_slot].item() == round(
            scalar_area.range * 1_000
        )
        assert result.areas.duration_ms[0, area_slot].item() == round(
            scalar_area.duration * 1_000
        )
        expected_movement = (
            scalar_area.movement_multiplier
            if isinstance(scalar_area, BuffAreaEffect)
            else scalar_area.speed_multiplier
        )
        assert (
            result.areas.movement_multiplier[0, area_slot].item() == expected_movement
        )
    if source_name == "IceGolem":
        for target in targets:
            assert (
                runtime.battle.entity_hp[0, _slot(runtime, target.id)].item()
                == oracle.entities[target.id].hitpoints
            )
    assert (
        runtime.events.opcode[0, : runtime.events.count[0]].tolist()[-1]
        == RuntimeEventOpcode.AREA
    )


def test_clone_fork_reset_and_area_capacity_rollback() -> None:
    battle, source, _ = _battle("Lumberjack")
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=8
    )
    state = TensorDeathPayloadState.from_battles(runtime, [battle], max_areas=1)
    clone = state.clone()
    fork = state.fork([0, 0])
    assert fork.areas.valid.shape == (2, 1)
    clone.areas.valid[0, 0] = True
    state.reset_rows_([0], clone, [0])
    before_id = runtime.entity_pool.next_entity_id.clone()
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, source.id)] = True

    result = step_death_payloads_(runtime, state, dead)

    assert result.committed.tolist() == [False]
    assert result.reason.tolist() == [DeathPayloadReason.AREA_CAPACITY]
    assert torch.equal(runtime.entity_pool.next_entity_id, before_id)
    assert runtime.events.count.tolist() == [0]


def test_event_capacity_rollback_is_row_local() -> None:
    first, source_a, _ = _battle("Golem")
    second = copy.deepcopy(first)
    runtime = TensorBattleRuntime.from_battles(
        [first, second], max_entities=8, event_capacity=2
    )
    state = TensorDeathPayloadState.from_battles(runtime, [first, second])
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[:, _slot(runtime, source_a.id)] = True
    runtime.events.append(
        phase=TickPhase.COMMANDS,
        opcode=RuntimeEventOpcode.COMMAND,
        valid=torch.tensor([[True], [False]]),
    )
    before = runtime.battle.entity_hp.clone()

    result = step_death_payloads_(runtime, state, dead)

    assert result.committed.tolist() == [False, True]
    assert result.reason.tolist() == [DeathPayloadReason.EVENT_CAPACITY, 0]
    assert torch.equal(runtime.battle.entity_hp[0], before[0])
    assert not torch.equal(runtime.battle.entity_hp[1], before[1])
