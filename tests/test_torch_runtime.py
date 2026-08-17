from __future__ import annotations

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import TargetType, Troop
from clasher.torch_sim.diagnostics import battle_snapshot, first_divergence
from clasher.torch_sim.executor import TorchBattleExecutor
from clasher.torch_sim.objects import (
    ObjectBlueprint,
    ObjectOpcode,
    TensorObjectCatalog,
    TensorObjectState,
)
from clasher.torch_sim.runtime import (
    PHASE_ORDER,
    RuntimeEventOpcode,
    TensorTickRuntime,
    TickPhase,
)


def _knight(
    battle: BattleState,
    entity_id: int,
    player_id: int,
    position: tuple[float, float],
    *,
    hp: float | None = None,
    cooldown: float = 10.0,
    deploy: float = 0.0,
) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    maximum = float(stats.scaled_hitpoints or stats.hitpoints or 1)
    entity = Troop(
        id=entity_id,
        position=Position(*position),
        player_id=player_id,
        card_stats=stats,
        hitpoints=maximum if hp is None else hp,
        max_hitpoints=maximum if hp is None else hp,
        damage=float(stats.scaled_damage or stats.damage or 0),
        range=float(stats.range or 0.0),
        sight_range=float(stats.sight_range or 0.0),
        speed=0.0,
        target_type=TargetType.GROUND,
        attack_cooldown=cooldown,
        deploy_delay_remaining=deploy,
        placement_delay_total=deploy,
        placement_pending=deploy > 0.0,
    )
    entity.battle_state = battle
    entity._spawn_hook_pending = deploy > 0.0
    entity._spawn_hook_fired = deploy <= 0.0
    return entity


def _battle_with(*entities: Troop) -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities = {entity.id: entity for entity in entities}
    battle.next_entity_id = max((entity.id for entity in entities), default=0) + 1
    for entity in entities:
        entity.battle_state = battle
    battle._win_conditions_dirty = True
    return battle


def _assert_exact(expected: BattleState, actual: BattleState) -> None:
    mismatch = first_divergence(battle_snapshot(expected), battle_snapshot(actual))
    assert mismatch is None, mismatch


def test_runtime_phase_order_is_the_exact_battle_manager_order() -> None:
    assert PHASE_ORDER == (
        TickPhase.CLOCK,
        TickPhase.PLAYER,
        TickPhase.ACTION_INGRESS,
        TickPhase.PROJECTILE_RESERVATION,
        TickPhase.COMBAT,
        TickPhase.MOVEMENT,
        TickPhase.BUILDING_LIFETIME,
        TickPhase.STATUS,
        TickPhase.OBJECT,
        TickPhase.CLEANUP,
        TickPhase.WIN,
    )


def test_complete_stationary_combat_tick_matches_oracle_through_cleanup() -> None:
    seed = BattleState(fast_path=False)
    attacker = _knight(seed, 1, 0, (9.0, 10.0), cooldown=0.0)
    target = _knight(seed, 2, 1, (9.0, 10.8), hp=100.0)
    battle = _battle_with(attacker, target)
    oracle = battle.clone()
    candidate = battle.clone()
    runtime = TensorTickRuntime.from_battles([candidate], max_entities=8)

    oracle.step_logic_ticks(1)
    result = runtime.step()
    runtime.sync_to_battles([candidate])

    assert result.supported.tolist() == [True]
    assert result.advanced.tolist() == [True]
    assert result.combat.attacked[0, 0].item() is True
    assert result.removed.entity_ids[0, 0].item() == 2
    opcodes = result.events.opcode[0, : result.events.count[0]].tolist()
    assert opcodes == [
        RuntimeEventOpcode.COMBAT_DAMAGE,
        RuntimeEventOpcode.ENTITY_DEATH,
    ]
    _assert_exact(oracle, candidate)


def test_deployment_object_frames_and_zero_crossing_match_oracle() -> None:
    seed = BattleState(fast_path=False)
    deploying = _knight(seed, 1, 0, (4.0, 8.0), deploy=0.1)
    battle = _battle_with(deploying)
    oracle = battle.clone()
    candidate = battle.clone()
    runtime = TensorTickRuntime.from_battles([candidate], max_entities=4)

    for tick in range(2):
        oracle.step_logic_ticks(1)
        result = runtime.step()
        runtime.sync_to_battles([candidate])
        assert result.supported.tolist() == [True]
        assert result.deployment_completed.tolist() == (
            [[False, False, False, False]]
            if tick == 0
            else [[True, False, False, False]]
        )
        _assert_exact(oracle, candidate)


def test_default_idle_battle_complete_tick_matches_oracle() -> None:
    battle = BattleState(fast_path=False)
    oracle = battle.clone()
    candidate = battle.clone()
    runtime = TensorTickRuntime.from_battles([candidate])

    oracle.step_logic_ticks(1)
    result = runtime.step()
    runtime.sync_to_battles([candidate])

    assert result.supported.tolist() == [True]
    _assert_exact(oracle, candidate)


def test_unsupported_batch_row_is_unchanged_while_neighbor_advances() -> None:
    supported = BattleState(fast_path=False)
    unsupported_seed = BattleState(fast_path=False)
    troop = _knight(unsupported_seed, 1, 0, (4.0, 8.0))
    troop.mechanics.append(object())
    unsupported = _battle_with(troop)
    before = battle_snapshot(unsupported)
    runtime = TensorTickRuntime.from_battles([supported, unsupported])
    retained_before = {
        (type(owner).__name__, name): value[1].clone()
        for owner in (
            runtime.core,
            runtime.pool,
            runtime.combat,
            runtime.status,
            runtime.objects,
            runtime.action_state,
        )
        for name, value in vars(owner).items()
        if isinstance(value, torch.Tensor) and value.ndim > 0 and value.shape[0] == 2
    }

    result = runtime.step()
    runtime.sync_to_battles([supported, unsupported])

    assert result.supported.tolist() == [True, False]
    assert result.advanced.tolist() == [True, False]
    assert result.unsupported_reasons[1] == (
        "character mechanics are outside stationary ordinary combat"
    )
    assert battle_snapshot(unsupported) == before
    assert supported.tick == 1
    for owner in (
        runtime.core,
        runtime.pool,
        runtime.combat,
        runtime.status,
        runtime.objects,
        runtime.action_state,
    ):
        for name, value in vars(owner).items():
            key = (type(owner).__name__, name)
            if key in retained_before:
                assert torch.equal(value[1], retained_before[key]), key


def test_dynamic_object_worklist_events_are_plumbed_into_runtime_stream() -> None:
    battle = BattleState(fast_path=False)
    runtime = TensorTickRuntime.from_battles([battle], max_objects=4)
    terminal = ObjectBlueprint(
        opcode=ObjectOpcode.PERIODIC_AREA,
        duration_ms=1,
        tick_interval_ms=50,
        initial_tick_ms=0,
        max_ticks=1,
        amount=7,
        inherit_terminal_position=True,
    )
    parent = ObjectBlueprint(
        opcode=ObjectOpcode.TIMED_PAYLOAD,
        activation_delay_ms=50,
        terminal_blueprint=1,
    )
    catalog = TensorObjectCatalog.compile([terminal, parent])
    runtime.objects = TensorObjectState.create(catalog, [[2]], max_objects=4)

    result = runtime.step()

    assert result.objects.processed_count.tolist() == [2]
    object_events = result.events.payload_opcode[0][
        result.events.opcode[0] == RuntimeEventOpcode.OBJECT_EVENT
    ].tolist()
    assert len(object_events) == 3
    assert torch.count_nonzero(runtime.objects.allocated).item() == 2


def test_custom_tick_duration_fails_closed_without_mutation() -> None:
    battle = BattleState(dt=0.1, fast_path=False)
    before = battle_snapshot(battle)
    runtime = TensorTickRuntime.from_battles([battle])

    result = runtime.step()
    runtime.sync_to_battles([battle])

    assert result.supported.tolist() == [False]
    assert result.advanced.tolist() == [False]
    assert result.unsupported_reasons == (
        "heterogeneous tick duration is not compiled",
    )
    assert battle_snapshot(battle) == before


def test_custom_phase_thresholds_match_oracle() -> None:
    battle = BattleState(
        fast_path=False,
        double_elixir_start_time=0.05,
        overtime_start_time=1.0,
        triple_elixir_start_time=0.05,
    )
    oracle = battle.clone()
    candidate = battle.clone()
    runtime = TensorTickRuntime.from_battles([candidate])

    oracle.step_logic_ticks(1)
    result = runtime.step()
    runtime.sync_to_battles([candidate])

    assert result.supported.tolist() == [True]
    _assert_exact(oracle, candidate)
    assert candidate.double_elixir
    assert candidate.triple_elixir


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_executor_routes_supported_stationary_combat_through_complete_runtime(
    backend: str,
) -> None:
    seed = BattleState(fast_path=False)
    attacker = _knight(seed, 1, 0, (9.0, 10.0), cooldown=0.0)
    target = _knight(seed, 2, 1, (9.0, 10.8), hp=100.0)
    battle = _battle_with(attacker, target)
    expected = battle.clone()
    expected.step_logic_ticks(1)

    executor = TorchBattleExecutor(backend)
    assert executor.step_logic_ticks(battle, 1) == 1

    _assert_exact(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 1
    assert executor.metrics_dict()["unsupported_fallbacks"] == 0


def test_executor_mixed_fast_runtime_and_fallback_rows_are_isolated() -> None:
    idle = BattleState(fast_path=False)
    seed = BattleState(fast_path=False)
    attacker = _knight(seed, 1, 0, (9.0, 10.0), cooldown=0.0)
    target = _knight(seed, 2, 1, (9.0, 10.8), hp=100.0)
    stationary = _battle_with(attacker, target)
    unsupported = _battle_with(_knight(seed, 1, 0, (4.0, 8.0)))
    unsupported.entities[1].speed = 1.0
    actual = [idle, stationary, unsupported]
    expected = [battle.clone() for battle in actual]
    for battle in expected:
        battle.step_logic_ticks(1)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_battles(actual, 1) == [1, 1, 1]

    for reference, candidate in zip(expected, actual):
        _assert_exact(reference, candidate)
    assert executor.metrics_dict()["tensor_ticks"] == 2
    assert executor.metrics_dict()["python_ticks"] == 1
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1
