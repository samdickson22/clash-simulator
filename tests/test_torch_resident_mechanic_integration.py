from __future__ import annotations

import copy

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.torch_sim.catalog import MECHANIC_OPCODE
from clasher.torch_sim.resident_engine import (
    ResidentUnsupportedReason,
    TensorResidentEngine,
)
from clasher.torch_sim.runtime_state import RuntimeEventOpcode


def _battle(
    source_name: str,
    *,
    target_hp: float | None = None,
    distance: float = 1.0,
) -> tuple[BattleState, int, int]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    source_stats = battle.card_loader.get_card(source_name)
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None and target_stats is not None
    source = battle._spawn_entity(Troop, Position(9.0, 10.0), 0, source_stats)
    target = battle._spawn_entity(
        Troop, Position(9.0, 10.0 + distance), 1, target_stats
    )
    for entity in (source, target):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    source.target_id = target.id
    source._movement_target_id = target.id  # type: ignore[attr-defined]
    source.attack_cooldown = 0.0
    target.attack_cooldown = 10.0
    if target_hp is not None:
        target.hitpoints = target_hp
    return battle, source.id, target.id


def _slot(engine: TensorResidentEngine, entity_id: int, row: int = 0) -> int:
    match = torch.nonzero(
        engine.runtime.battle.entity_id[row] == entity_id, as_tuple=False
    ).flatten()
    assert match.numel() == 1
    return int(match.item())


@pytest.mark.parametrize("target_hp", (None, 100.0))
def test_resident_serialized_on_hit_matches_nonlethal_and_lethal_python(
    target_hp: float | None,
) -> None:
    battle, source_id, target_id = _battle("MiniSparkys", target_hp=target_hp)
    oracle = copy.deepcopy(battle)
    oracle.step_logic_ticks(1)
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=8, event_capacity=64
    )
    target_slot = _slot(engine, target_id)

    result = engine.step()

    assert result.committed.tolist() == [True]
    if target_id in oracle.entities:
        assert engine.runtime.entity_pool.active[0, target_slot].item()
        assert engine.runtime.battle.entity_hp[0, target_slot].item() == (
            oracle.entities[target_id].hitpoints
        )
        assert engine.runtime.status.stun_timer[0, target_slot].item() == (
            oracle.entities[target_id].stun_timer
        )
        count = int(engine.runtime.events.count[0].item())
        damage_events = (
            engine.runtime.events.opcode[0, :count] == int(RuntimeEventOpcode.DAMAGE)
        ) & (engine.runtime.events.target_id[0, :count] == target_id)
        assert damage_events.sum().item() == 1
    else:
        assert not engine.runtime.entity_pool.active[0, target_slot].item()
        count = int(engine.runtime.events.count[0].item())
        status_callback = (
            (engine.runtime.events.opcode[0, :count] == int(RuntimeEventOpcode.STATUS))
            & (engine.runtime.events.source_id[0, :count] == source_id)
            & (engine.runtime.events.target_id[0, :count] == target_id)
        )
        assert status_callback.any().item()


def test_resident_skeleton_king_collects_dead_enemy_before_cleanup() -> None:
    battle, source_id, target_id = _battle("SkeletonKing")
    target = battle.entities[target_id]
    target.hitpoints = 0.0
    target.is_alive = False
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=8, event_capacity=64
    )
    source_slot = _slot(engine, source_id)

    result = engine.step()

    assert result.committed.tolist() == [True]
    assert engine.dispatcher.passive.souls_collected[0, source_slot].item() == 1
    assert target_id not in engine.runtime.battle.entity_id[0].tolist()


def test_resident_bandit_full_dash_matches_stationary_python_target() -> None:
    battle, source_id, target_id = _battle("Bandit", distance=5.0)
    battle.entities[target_id].stun_timer = 100.0
    oracle = copy.deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=16, event_capacity=256
    )
    source_slot = _slot(engine, source_id)
    target_slot = _slot(engine, target_id)
    initial_hp = oracle.entities[target_id].hitpoints

    for _ in range(32):
        oracle.step_logic_ticks(1)
        result = engine.step()
        assert result.committed.tolist() == [True]
        assert engine.runtime.battle.entity_x_units[0, source_slot].item() == round(
            oracle.entities[source_id].position.x * 1_000
        )
        assert engine.runtime.battle.entity_y_units[0, source_slot].item() == round(
            oracle.entities[source_id].position.y * 1_000
        )
        assert engine.runtime.battle.entity_hp[0, target_slot].item() == (
            oracle.entities[target_id].hitpoints
        )
        if oracle.entities[target_id].hitpoints < initial_hp:
            break
    else:
        pytest.fail("resident Bandit dash did not land")


def test_resident_mechanic_mixed_rows_commit_atomically() -> None:
    supported, _, target_id = _battle("MiniSparkys")
    unsupported, _, _ = _battle("ArcherQueen")
    engine = TensorResidentEngine.from_battles(
        [supported, unsupported], max_entities=8, max_objects=8, event_capacity=64
    )
    unsupported_before = engine.runtime.battle.entity_hp[1].clone()
    unsupported_time = engine.runtime.battle.time[1].clone()

    preflight = engine.preflight()
    result = engine.step()

    assert preflight.supported.tolist() == [True, False]
    assert preflight.reason_code.tolist() == [
        ResidentUnsupportedReason.NONE,
        ResidentUnsupportedReason.ACTIVE_MECHANIC,
    ]
    assert preflight.mechanic_opcode_present[
        1, MECHANIC_OPCODE["ArcherQueenCloak"]
    ].item()
    assert result.committed.tolist() == [True, False]
    assert engine.runtime.battle.entity_hp[0, _slot(engine, target_id, 0)].item() < (
        supported.entities[target_id].hitpoints
    )
    assert torch.equal(engine.runtime.battle.entity_hp[1], unsupported_before)
    assert torch.equal(engine.runtime.battle.time[1], unsupported_time)


def test_unintegrated_champion_mechanic_remains_preflight_fallback() -> None:
    battle, _, _ = _battle("ArcherQueen")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=8, event_capacity=64
    )

    preflight = engine.preflight()

    assert preflight.supported.tolist() == [False]
    assert preflight.reason_code.tolist() == [ResidentUnsupportedReason.ACTIVE_MECHANIC]


def test_resident_integrated_death_area_owner_preflight_and_tick_commit() -> None:
    battle, source_id, _ = _battle("IceGolem")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=8, event_capacity=64
    )
    source_slot = _slot(engine, source_id)

    preflight = engine.preflight()
    owner_supported = engine._death_payload_entity_supported()[0, source_slot]
    result = engine.step()

    assert preflight.supported.tolist() == [True]
    assert preflight.reason_code.tolist() == [ResidentUnsupportedReason.NONE]
    assert preflight.mechanic_opcode_present[
        0, MECHANIC_OPCODE["DeathAreaEffect"]
    ].item()
    assert owner_supported.item()
    assert result.committed.tolist() == [True]
    assert result.death_payloads is not None
    assert result.death_payloads.committed.tolist() == [True]


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_resident_mechanic_mixed_rows_smoke() -> None:
    battle, source_id, target_id = _battle("Bandit", distance=5.0)
    unsupported, _, _ = _battle("ArcherQueen")
    battle.entities[target_id].stun_timer = 100.0
    engine = TensorResidentEngine.from_battles(
        [battle, unsupported],
        device="cuda",
        max_entities=8,
        max_objects=8,
        event_capacity=64,
    )

    result = engine.step()

    assert result.committed.tolist() == [True, False]
    assert engine.dispatcher.dash.phase[0, _slot(engine, source_id)].item() != 0
