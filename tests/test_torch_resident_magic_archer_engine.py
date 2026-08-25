from __future__ import annotations

import copy
import random
from collections import deque
from typing import Any

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.diagnostics import first_divergence
from clasher.torch_sim.oracle_event_capture import PythonOracleEventCapture
from clasher.torch_sim.resident_differential import (
    _oracle_events,
    _oracle_snapshot,
    _resident_events,
    _resident_snapshot,
)
from clasher.torch_sim.resident_engine import (
    ResidentTickResult,
    ResidentUnsupportedReason,
    TensorResidentEngine,
)
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = battle._spawn_entity(Troop, position, player, stats)
    assert isinstance(entity, Troop)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.attack_cooldown = 10.0
    entity.stun_timer = 100.0
    return entity


def _shield(entity: Troop) -> Any:
    return next(
        mechanic for mechanic in entity.mechanics if type(mechanic).__name__ == "Shield"
    )


def _slot(engine: TensorResidentEngine, entity_id: int, row: int = 0) -> int:
    slots = torch.nonzero(
        engine.runtime.battle.entity_id[row] == entity_id,
        as_tuple=False,
    ).flatten()
    assert slots.numel() == 1
    return int(slots.item())


def _battle(*, shield: bool = False, lethal: bool = False) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(8_241_001))
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn(battle, "MagicArcher", 0, Position(9.0, 10.0))
    target_name = "Guards" if shield else "Knight"
    primary = _spawn(battle, target_name, 1, Position(9.0, 15.0))
    later = _spawn(battle, "Knight", 1, Position(9.0, 17.0))
    source.target_id = primary.id
    source._movement_target_id = primary.id
    source.attack_cooldown = 0.0
    source.stun_timer = 0.0
    if lethal:
        primary.hitpoints = source.damage
        later.hitpoints = source.damage
    return battle


def _engine(battles: list[BattleState], device: str) -> TensorResidentEngine:
    return TensorResidentEngine.from_battles(
        battles,
        device=device,
        max_entities=24,
        max_objects=16,
        event_capacity=512,
    )


def _assert_exact_tick(
    engine: TensorResidentEngine,
    workspace: TensorResidentWorkspace,
    oracle: BattleState,
    *,
    actions: torch.Tensor | None = None,
) -> ResidentTickResult:
    event_start = int(engine.runtime.events.count[0].item())
    with PythonOracleEventCapture(oracle) as capture:
        if actions is not None:
            action = int(actions[0, 0].item())
            action_space = DiscreteTileActionSpace(canonical_perspective=True)
            assert capture.command(lambda: action_space.apply_action(oracle, 0, action))
        capture.step_logic_ticks(1)
    result = workspace.step(
        actions,
        player_order=torch.tensor([[0, 1]], device=engine.device),
    )
    assert result.committed.tolist() == [True], (
        workspace.scratch.runtime.phases.supported,
        result.preflight,
        result.piercing_launch,
        result.piercing_projectiles,
    )
    assert _resident_events(engine, 0, event_start) == _oracle_events(
        capture.events, engine
    )
    divergence = first_divergence(
        _oracle_snapshot(oracle),
        _resident_snapshot(engine, 0),
    )
    assert divergence is None, divergence
    assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
    return result


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_predeployed_magic_archer_full_launch_expiry_matches_oracle(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    boundary = _battle()
    oracle = copy.deepcopy(boundary)
    engine = _engine([boundary], device)
    workspace = TensorResidentWorkspace(engine)
    order = torch.tensor([[0, 1]], device=engine.device)

    assert engine.preflight().supported.tolist() == [True]
    launched = False
    for tick in range(30):
        event_start = int(engine.runtime.events.count[0].item())
        with PythonOracleEventCapture(oracle) as capture:
            capture.step_logic_ticks(1)
        result = workspace.step(player_order=order)
        assert result.committed.tolist() == [True], (
            tick,
            result.piercing_launch,
            result.piercing_projectiles,
            result.rolling_combat_materialization,
            workspace.scratch.runtime.phases.supported,
            workspace.scratch.runtime.supported,
            engine.diagnose_preflight(),
        )
        launched |= bool(result.piercing_launch.accepted.item())
        assert _resident_events(engine, 0, event_start) == _oracle_events(
            capture.events, engine
        )
        divergence = first_divergence(
            _oracle_snapshot(oracle),
            _resident_snapshot(engine, 0),
        )
        assert divergence is None, f"tick={tick}: {divergence}"
        assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
        if launched and not engine.piercing_projectiles.active.any():
            break

    assert launched
    assert not engine.piercing_projectiles.active.any()


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_live_piercing_boundary_is_pruned_from_generic_objects_and_expires(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    boundary = _battle()
    source = boundary.entities[1]
    primary = boundary.entities[2]
    assert isinstance(source, Troop) and isinstance(primary, Troop)
    source._create_projectile(primary, boundary)
    source.attack_cooldown = 10.0
    oracle = copy.deepcopy(boundary)
    engine = _engine([boundary], device)
    workspace = TensorResidentWorkspace(engine)

    assert engine.piercing_projectiles.active.sum().item() == 1
    assert not engine.objects.objects.allocated.any()
    assert engine.preflight().supported.tolist() == [True]
    for _ in range(20):
        _assert_exact_tick(engine, workspace, oracle)
        if not engine.piercing_projectiles.active.any():
            break

    assert not engine.piercing_projectiles.active.any()


def test_active_piercing_coexistence_remains_fail_closed() -> None:
    boundary = _battle()
    source = boundary.entities[1]
    primary = boundary.entities[2]
    assert isinstance(source, Troop) and isinstance(primary, Troop)
    source._create_projectile(primary, boundary)
    source.attack_cooldown = 10.0
    engine = _engine([boundary], "cpu")
    assert engine.preflight().supported.tolist() == [True]

    conflicts = []
    generic = engine.clone()
    generic.objects.objects.allocated[0, 0] = True
    generic.objects.objects.active[0, 0] = True
    conflicts.append(generic)
    rolling = engine.clone()
    rolling.rolling_combat.state.active[0, 0] = True
    conflicts.append(rolling)
    timed = engine.clone()
    timed.terminal_pipeline.state.objects.allocated[0, 0] = True
    conflicts.append(timed)
    area = engine.clone()
    area.continuous_areas.active[0, 0] = True
    conflicts.append(area)
    chain = engine.clone()
    chain.chain_impacts.active[0, 0] = True
    conflicts.append(chain)
    multiple = engine.clone()
    multiple.piercing_projectiles.active[0, 1] = True
    conflicts.append(multiple)

    for conflict in conflicts:
        preflight = conflict.preflight()
        assert preflight.supported.tolist() == [False]
        assert preflight.reason_code.tolist() == [
            int(ResidentUnsupportedReason.OBJECT_PHASE)
        ]

    periodic_boundary = _battle()
    tombstone_stats = periodic_boundary.card_loader.get_card("Tombstone")
    assert tombstone_stats is not None
    tombstone = periodic_boundary._spawn_entity(
        Building,
        Position(3.0, 8.0),
        0,
        tombstone_stats,
    )
    tombstone.deploy_delay_remaining = 0.0
    tombstone.placement_pending = False
    periodic_source = periodic_boundary.entities[1]
    periodic_primary = periodic_boundary.entities[2]
    assert isinstance(periodic_source, Troop) and isinstance(periodic_primary, Troop)
    periodic_source._create_projectile(periodic_primary, periodic_boundary)
    periodic_source.attack_cooldown = 10.0
    periodic = _engine([periodic_boundary], "cpu").preflight()
    assert periodic.supported.tolist() == [False]
    assert periodic.reason_code.tolist() == [
        int(ResidentUnsupportedReason.OBJECT_PHASE)
    ]


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_real_magic_archer_action_reaches_first_piercing_impact(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    boundary = BattleState(fast_path=False, rng=random.Random(8_241_002))
    boundary.entities.clear()
    boundary.next_entity_id = 1
    target = _spawn(boundary, "Knight", 1, Position(9.5, 20.0))
    target.hitpoints = 2_000.0
    target.max_hitpoints = 2_000.0
    player = boundary.players[0]
    player.hand = ["MagicArcher", "Knight", "Cannon", "Zap"]
    player.deck = [name for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 10.0
    oracle = copy.deepcopy(boundary)
    engine = _engine([boundary], device)
    workspace = TensorResidentWorkspace(engine)
    action = DiscreteTileActionSpace(canonical_perspective=True).encode_action(
        0, 9, 14, 0
    )
    actions = torch.tensor([[action, NO_OP_ACTION]], device=engine.device)
    initial_hp = target.hitpoints

    first = _assert_exact_tick(engine, workspace, oracle, actions=actions)
    assert first.deployment.committed.tolist() == [True]
    for _ in range(99):
        _assert_exact_tick(engine, workspace, oracle)
        if oracle.entities[target.id].hitpoints < initial_hp:
            break

    assert oracle.entities[target.id].hitpoints < initial_hp
    target_slot = _slot(engine, target.id)
    assert engine.runtime.battle.entity_hp[0, target_slot].item() == (
        oracle.entities[target.id].hitpoints
    )


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_piercing_shield_absorb_then_lethal_preserves_order(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    boundary = _battle(shield=True, lethal=True)
    oracle = copy.deepcopy(boundary)
    engine = _engine([boundary], device)
    workspace = TensorResidentWorkspace(engine)

    for _ in range(30):
        _assert_exact_tick(engine, workspace, oracle)
        if not engine.piercing_projectiles.active.any() and 3 not in oracle.entities:
            break

    guard = oracle.entities[2]
    assert isinstance(guard, Troop)
    guard_slot = _slot(engine, 2)
    guard_shield = _shield(guard)
    assert engine.mechanics.shield_current[0, guard_slot].item() == float(
        guard_shield.current_shield
    )
    assert engine.mechanics.shield_break_count[0, guard_slot].item() == getattr(
        guard, "_shield_break_count", 0
    )
    assert engine.shield_integer_kind[0, guard_slot].item() is (
        type(guard_shield.current_shield) is int
    )
    assert 3 not in oracle.entities
    assert 3 not in engine.runtime.battle.entity_id[0].tolist()


def test_piercing_launch_capacity_failure_rolls_back_whole_engine_row() -> None:
    boundary = _battle()
    engine = TensorResidentEngine.from_battles(
        [boundary],
        max_entities=3,
        max_objects=4,
        event_capacity=64,
    )
    workspace = TensorResidentWorkspace(engine)
    before = engine.clone()

    result = workspace.step(player_order=torch.tensor([[0, 1]]))

    assert result.committed.tolist() == [False]
    assert result.piercing_launch.capacity_rejected.tolist() == [True]
    assert torch.equal(engine.runtime.battle.tick, before.runtime.battle.tick)
    assert torch.equal(engine.runtime.battle.time, before.runtime.battle.time)
    assert torch.equal(
        engine.runtime.entity_pool.next_entity_id,
        before.runtime.entity_pool.next_entity_id,
    )
    assert torch.equal(engine.runtime.events.count, before.runtime.events.count)
    assert not engine.piercing_projectiles.active.any()
    assert engine.runtime.battle.rng.python_state(0) == (
        before.runtime.battle.rng.python_state(0)
    )


def test_clone_workspace_and_mixed_rows_retain_piercing_owner() -> None:
    engine = _engine([_battle(), BattleState(fast_path=False)], "cpu")
    clone = engine.clone()
    workspace = TensorResidentWorkspace(engine)

    assert clone.piercing_projectiles.catalog is engine.piercing_projectiles.catalog
    assert workspace.scratch.piercing_projectiles.catalog is (
        engine.piercing_projectiles.catalog
    )
    assert clone.piercing_projectiles.active.data_ptr() != (
        engine.piercing_projectiles.active.data_ptr()
    )
    assert workspace.scratch.piercing_projectiles.active.data_ptr() != (
        engine.piercing_projectiles.active.data_ptr()
    )

    result = workspace.step(player_order=torch.tensor([[0, 1], [0, 1]]))
    assert result.committed.tolist() == [True, True]
    assert result.piercing_launch.accepted.tolist() == [True, False]
    assert engine.piercing_projectiles.active.tolist()[1] == [False] * (
        engine.piercing_projectiles.capacity
    )
