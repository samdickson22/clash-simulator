from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.combat import StationaryCombatState, step_stationary_combat_
from clasher.torch_sim.oracle_event_capture import PythonOracleEventCapture
from clasher.torch_sim.resident_differential import _oracle_events, _resident_events
from clasher.torch_sim.resident_engine import (
    ResidentUnsupportedReason,
    TensorResidentEngine,
)
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Entity:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    kind = Building if str(stats.card_type).lower() == "building" else Troop
    entity = battle._spawn_entity(kind, position, player, stats)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _set_hand(battle: BattleState, player: int, first: str) -> None:
    owner = battle.players[player]
    owner.hand = [first, "Knight", "Cannon", "Zap"]
    owner.deck = [name for name in owner.hand if name is not None]
    owner.cycle_queue = deque()
    owner.elixir = 20.0


def _battle(
    *,
    target_hp: float = 100_000.0,
    target_name: str = "Golem",
) -> tuple[BattleState, int, int]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    _set_hand(battle, 0, "InfernoTower")
    _set_hand(battle, 1, "Zap")
    tower = _spawn(battle, "InfernoTower", 0, Position(9.0, 12.0))
    target = _spawn(battle, target_name, 1, Position(9.0, 14.0))
    target.hitpoints = target_hp
    target.max_hitpoints = target_hp
    target.attack_cooldown = 100.0
    target.stun_timer = 100.0
    tower.target_id = target.id
    return battle, tower.id, target.id


def _slot(engine: TensorResidentEngine, entity_id: int) -> int:
    slots = torch.nonzero(
        engine.runtime.battle.entity_id[0] == entity_id,
        as_tuple=False,
    ).flatten()
    assert slots.numel() == 1
    return int(slots.item())


def _ramp(entity: Entity) -> Any:
    return next(
        mechanic
        for mechanic in entity.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )


def _assert_ramp_matches(
    engine: TensorResidentEngine,
    oracle: BattleState,
    tower_id: int,
) -> None:
    slot = _slot(engine, tower_id)
    tower = oracle.entities[tower_id]
    ramp = _ramp(tower)
    assert engine.combat.damage_ramp_source_id[0, slot].item() == tower_id
    assert engine.combat.damage_ramp_target_id[0, slot].item() == int(
        ramp._current_target_id or 0
    )
    assert engine.combat.damage_ramp_connected_ms[0, slot].item() == pytest.approx(
        ramp._current_target_ms
    )
    assert engine.combat.damage[0, slot].item() == float(tower.damage)
    assert engine.combat.attack_cooldown[0, slot].item() == pytest.approx(
        tower.attack_cooldown
    )


def test_active_inferno_tower_multistage_state_rng_and_events_match_oracle(
    tensor_device: str,
) -> None:
    battle, tower_id, target_id = _battle()
    oracle = deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=tensor_device,
        max_entities=16,
        max_objects=16,
        event_capacity=2_048,
    )
    observed_stages: list[int] = []

    for tick in range(80):
        event_start = int(engine.runtime.events.count[0].item())
        with PythonOracleEventCapture(oracle) as capture:
            capture.step_logic_ticks(1)
        result = engine.step(player_order=torch.tensor([[0, 1]], device=engine.device))

        assert result.committed.tolist() == [True], tick
        assert _resident_events(engine, 0, event_start) == _oracle_events(
            capture.events, engine
        )
        assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
        _assert_ramp_matches(engine, oracle, tower_id)
        target_slot = _slot(engine, target_id)
        assert engine.runtime.battle.entity_hp[0, target_slot].item() == float(
            oracle.entities[target_id].hitpoints
        )
        observed_stages.append(
            int(engine.combat.damage_ramp_stage[0, _slot(engine, tower_id)].item())
        )

    assert observed_stages[38:40] == [0, 1]
    assert observed_stages[78:80] == [1, 2]


def test_inferno_tower_action_is_admitted_but_inferno_dragon_fails_closed(
    tensor_device: str,
) -> None:
    battle = BattleState(fast_path=False)
    _set_hand(battle, 0, "InfernoTower")
    oracle = battle.clone()
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=tensor_device,
        max_entities=24,
        max_objects=16,
        event_capacity=256,
    )
    legal = engine.deployment.kernel.legal_action_mask(
        engine.deployment.action_state(engine.runtime)
    )
    action = int(torch.nonzero(legal[0, 0, : 18 * 32], as_tuple=False)[0, 0])
    actions = torch.tensor([[action, NO_OP_ACTION]], device=engine.device)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    with PythonOracleEventCapture(oracle) as capture:
        assert capture.command(lambda: action_space.apply_action(oracle, 0, action))
        capture.step_logic_ticks(1)

    result = engine.step(
        actions,
        player_order=torch.tensor([[0, 1]], device=engine.device),
    )

    assert result.committed.tolist() == [True]
    assert _resident_events(engine, 0, 0) == _oracle_events(capture.events, engine)
    assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
    owner = engine.mechanic_deployment.catalog.owner_index("damage_ramp")
    source_ids = engine.mechanic_deployment.state.owner_entity_id[owner, 0]
    assert (source_ids > 0).sum().item() == 1
    tower_id = int(source_ids.max().item())
    tower_slot = _slot(engine, tower_id)
    assert engine.combat.damage_ramp_enabled[0, tower_slot].item()

    dragon = BattleState(fast_path=False)
    _set_hand(dragon, 0, "InfernoDragon")
    dragon_engine = TensorResidentEngine.from_battles(
        [dragon], max_entities=24, max_objects=16, event_capacity=128
    )
    dragon_legal = dragon_engine.deployment.kernel.legal_action_mask(
        dragon_engine.deployment.action_state(dragon_engine.runtime)
    )
    dragon_action = int(
        torch.nonzero(dragon_legal[0, 0, : 18 * 32], as_tuple=False)[0, 0]
    )
    dragon_actions = torch.tensor([[dragon_action, NO_OP_ACTION]])
    before = dragon_engine.runtime.battle.entity_id.clone()
    dragon_result = dragon_engine.step(dragon_actions)
    assert dragon_engine.preflight(dragon_actions).reason_code.tolist() == [
        ResidentUnsupportedReason.ACTION_MECHANIC
    ]
    assert dragon_result.committed.tolist() == [False]
    assert torch.equal(dragon_engine.runtime.battle.entity_id, before)

    active_dragon = BattleState(fast_path=False)
    active_dragon.entities.clear()
    active_dragon.next_entity_id = 1
    _set_hand(active_dragon, 0, "InfernoDragon")
    dragon_source = _spawn(active_dragon, "InfernoDragon", 0, Position(9.0, 12.0))
    dragon_target = _spawn(active_dragon, "Knight", 1, Position(9.0, 14.0))
    dragon_source.target_id = dragon_target.id
    active_engine = TensorResidentEngine.from_battles(
        [active_dragon], max_entities=16, max_objects=16, event_capacity=128
    )
    assert active_engine.preflight().reason_code.tolist() == [
        ResidentUnsupportedReason.ACTIVE_MECHANIC
    ]


def test_target_death_reacquire_uses_exact_retarget_clock(
    tensor_device: str,
) -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    _set_hand(battle, 0, "InfernoTower")
    _set_hand(battle, 1, "Knight")
    tower = _spawn(battle, "InfernoTower", 0, Position(9.0, 12.0))
    first = _spawn(battle, "Knight", 1, Position(9.0, 14.0))
    first.hitpoints = 43.0
    first.max_hitpoints = 43.0
    first.attack_cooldown = 100.0
    first.stun_timer = 100.0
    second = _spawn(battle, "Knight", 1, Position(10.0, 14.0))
    second.hitpoints = 100_000.0
    second.max_hitpoints = 100_000.0
    second.attack_cooldown = 100.0
    second.stun_timer = 100.0
    tower.attack_cooldown = 0.0
    tower.target_id = first.id
    tower_id = tower.id
    first_id = first.id
    oracle = deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=tensor_device,
        max_entities=16,
        max_objects=16,
        event_capacity=256,
    )

    first_tick = engine.step()
    oracle.step_logic_ticks(1)
    assert first_tick.committed.tolist() == [True]
    assert first_id not in oracle.entities
    assert first_id not in engine.runtime.battle.entity_id[0].tolist()

    second_tick = engine.step()
    oracle.step_logic_ticks(1)
    assert second_tick.committed.tolist() == [True]
    _assert_ramp_matches(engine, oracle, tower_id)
    tower_slot = _slot(engine, tower_id)
    assert (
        engine.combat.damage_ramp_observed_target_id[0, tower_slot].item() == second.id
    )
    assert engine.combat.attack_cooldown[0, tower_slot].item() == pytest.approx(0.75)
    assert engine.combat.damage_ramp_connected_ms[0, tower_slot].item() == 50.0


def test_lower_id_shield_break_resets_higher_id_ramp_before_same_tick_hit(
    tensor_device: str,
) -> None:
    def run(entity_ids: tuple[int, int, int]) -> tuple[float, float, float, int]:
        state = StationaryCombatState.empty(1, 3, device=tensor_device)
        state.present[0] = True
        state.alive[0] = True
        state.entity_id[0] = torch.tensor(entity_ids, device=state.device)
        ordinary = entity_ids.index(10)
        inferno = entity_ids.index(20)
        target = entity_ids.index(40)
        state.owner[0, target] = 1
        state.x_units[0] = 9_000
        state.y_units[0] = 12_000
        state.hp[0] = 1_000.0
        state.max_hp[0] = 1_000.0
        state.damage[0, ordinary] = 1.0
        state.damage[0, inferno] = 847.0
        state.range_units[0] = 1_000
        state.sight_range_units[0] = 5_500
        state.can_attack_ground[0] = True
        state.attack_cooldown[0] = 0.0
        state.combat_enabled[0, target] = False
        state.has_shield[0, target] = True
        state.shield_hp[0, target] = 1.0
        state.damage_ramp_enabled[0, inferno] = True
        state.damage_ramp_source_id[0, inferno] = 20
        state.damage_ramp_observed_target_id[0, inferno] = 40
        state.damage_ramp_target_id[0, inferno] = 40
        state.damage_ramp_connected_ms[0, inferno] = 4_000.0
        state.damage_ramp_stage[0, inferno] = 2
        state.damage_ramp_stage_1_ms[0, inferno] = 2_000
        state.damage_ramp_stage_2_ms[0, inferno] = 4_000
        state.damage_ramp_stage_0_damage[0, inferno] = 43.0
        state.damage_ramp_stage_1_damage[0, inferno] = 158.0
        state.damage_ramp_stage_2_damage[0, inferno] = 847.0
        state.damage_ramp_beam_range_units[0, inferno] = 1_000
        state.damage_ramp_retarget_ms[0, inferno] = 800
        state.target_slot[0, ordinary] = target
        state.target_slot[0, inferno] = target

        step_stationary_combat_(state)

        return (
            float(state.shield_hp[0, target].item()),
            float(state.hp[0, target].item()),
            float(state.damage_ramp_connected_ms[0, inferno].item()),
            int(state.damage_ramp_stage[0, inferno].item()),
        )

    expected = (0.0, 957.0, 50.0, 0)
    assert run((10, 20, 40)) == expected
    assert run((40, 20, 10)) == expected


def test_beam_reach_is_stricter_than_retained_keep_reach(
    tensor_device: str,
) -> None:
    state = StationaryCombatState.empty(1, 2, device=tensor_device)
    state.present[0] = True
    state.alive[0] = True
    state.entity_id[0] = torch.tensor([10, 20], device=state.device)
    state.owner[0, 1] = 1
    state.x_units[0] = torch.tensor([9_000, 10_510], device=state.device)
    state.y_units[0] = 12_000
    state.hp[0] = 1_000.0
    state.max_hp[0] = 1_000.0
    state.range_units[0, 0] = 1_000
    state.sight_range_units[0, 0] = 5_500
    state.can_attack_ground[0, 0] = True
    state.combat_enabled[0, 1] = False
    state.target_slot[0, 0] = 1
    state.damage_ramp_enabled[0, 0] = True
    state.damage_ramp_source_id[0, 0] = 10
    state.damage_ramp_observed_target_id[0, 0] = 20
    state.damage_ramp_target_id[0, 0] = 20
    state.damage_ramp_connected_ms[0, 0] = 4_000.0
    state.damage_ramp_stage[0, 0] = 2
    state.damage_ramp_stage_1_ms[0, 0] = 2_000
    state.damage_ramp_stage_2_ms[0, 0] = 4_000
    state.damage_ramp_stage_0_damage[0, 0] = 43.0
    state.damage_ramp_stage_1_damage[0, 0] = 158.0
    state.damage_ramp_stage_2_damage[0, 0] = 847.0
    state.damage_ramp_beam_range_units[0, 0] = 1_000
    state.damage_ramp_retarget_ms[0, 0] = 800

    result = step_stationary_combat_(state)

    assert result.target_after.tolist() == [[1, -1]]
    assert result.attack_clock_in_range is not None
    assert not result.attack_clock_in_range[0, 0].item()
    assert state.damage_ramp_observed_target_id[0, 0].item() == 20
    assert state.damage_ramp_target_id[0, 0].item() == 0
    assert state.damage_ramp_connected_ms[0, 0].item() == 0
    assert state.damage[0, 0].item() == 43.0


def test_zap_resets_connected_ramp_and_matches_oracle(tensor_device: str) -> None:
    battle, tower_id, _ = _battle(target_name="Knight")
    tower = battle.entities[tower_id]
    ramp = _ramp(tower)
    ramp._current_target_id = tower.target_id
    ramp._current_target_ms = 4_100.0
    tower.damage = ramp.stages[-1][1]
    oracle = deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=tensor_device,
        max_entities=16,
        max_objects=16,
        event_capacity=512,
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    action = action_space.encode_action(0, 9, 12, 1)
    actions = torch.tensor([[NO_OP_ACTION, action]], device=engine.device)
    assert action_space.apply_action(oracle, 1, action)

    reset_seen = False
    for tick in range(24):
        result = engine.step(actions if tick == 0 else None)
        oracle.step_logic_ticks(1)
        assert result.committed.tolist() == [True], tick
        _assert_ramp_matches(engine, oracle, tower_id)
        scalar_tower = oracle.entities[tower_id]
        if scalar_tower.stun_timer > 0:
            tower_slot = _slot(engine, tower_id)
            assert engine.combat.damage_ramp_target_id[0, tower_slot].item() == 0
            assert engine.combat.damage_ramp_connected_ms[0, tower_slot].item() == 0
            assert engine.combat.damage_ramp_stage[0, tower_slot].item() == 0
            assert engine.combat.damage[0, tower_slot].item() == 43.0
            reset_seen = True
            break

    assert reset_seen


def test_final_attack_precedes_intrinsic_lifetime_death(tensor_device: str) -> None:
    battle, tower_id, target_id = _battle()
    tower = battle.entities[tower_id]
    tower.attack_cooldown = 0.0
    # One native lifetime quantum is two HP for this scaled tower. Matching
    # that exact remainder exercises the final combat-before-lifetime order.
    tower.hitpoints = 2.0
    oracle = deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=tensor_device,
        max_entities=16,
        max_objects=16,
        event_capacity=128,
    )
    before = oracle.entities[target_id].hitpoints

    with PythonOracleEventCapture(oracle) as capture:
        capture.step_logic_ticks(1)
    result = engine.step()

    assert result.committed.tolist() == [True]
    assert tower_id not in oracle.entities
    assert tower_id not in engine.runtime.battle.entity_id[0].tolist()
    assert oracle.entities[target_id].hitpoints == before - 43
    assert _resident_events(engine, 0, 0) == _oracle_events(capture.events, engine)


def test_event_capacity_failure_rolls_back_ramp_context_and_runtime() -> None:
    battle, tower_id, target_id = _battle(target_hp=43.0)
    battle.entities[tower_id].attack_cooldown = 0.0
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=16, event_capacity=1
    )
    workspace = TensorResidentWorkspace(engine)
    engine.runtime.events.count.fill_(engine.runtime.events.capacity)
    before_hp = engine.runtime.battle.entity_hp.clone()
    before_time = engine.runtime.battle.time.clone()
    before_rng = engine.runtime.battle.rng.python_state(0)
    before_ramp = engine.combat.damage_ramp_connected_ms.clone()

    result = workspace.step()

    assert result.committed.tolist() == [False]
    assert torch.equal(engine.runtime.battle.entity_hp, before_hp)
    assert torch.equal(engine.runtime.battle.time, before_time)
    assert engine.runtime.battle.rng.python_state(0) == before_rng
    assert torch.equal(engine.combat.damage_ramp_connected_ms, before_ramp)
    assert target_id in engine.runtime.battle.entity_id[0].tolist()


def test_cleanup_slot_reuse_installs_fresh_ramp_source_identity(
    tensor_device: str,
) -> None:
    battle, tower_id, _ = _battle()
    tower = battle.entities[tower_id]
    tower.hitpoints = 2.0
    tower.attack_cooldown = 10.0
    oracle = deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=tensor_device,
        max_entities=16,
        max_objects=16,
        event_capacity=256,
    )
    reused_slot = _slot(engine, tower_id)

    assert engine.step().committed.tolist() == [True]
    oracle.step_logic_ticks(1)
    assert tower_id not in engine.runtime.battle.entity_id[0].tolist()
    assert tower_id not in oracle.entities

    legal = engine.deployment.kernel.legal_action_mask(
        engine.deployment.action_state(engine.runtime)
    )
    action = int(torch.nonzero(legal[0, 0, : 18 * 32], as_tuple=False)[0, 0])
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    assert action_space.apply_action(oracle, 0, action)
    actions = torch.tensor([[action, NO_OP_ACTION]], device=engine.device)
    result = engine.step(
        actions,
        player_order=torch.tensor([[0, 1]], device=engine.device),
    )
    oracle.step_logic_ticks(1)

    assert result.committed.tolist() == [True]
    new_id = max(oracle.entities)
    assert _slot(engine, new_id) == reused_slot
    assert engine.combat.damage_ramp_source_id[0, reused_slot].item() == new_id
    assert engine.combat.damage_ramp_target_id[0, reused_slot].item() == 0
    assert engine.combat.damage_ramp_connected_ms[0, reused_slot].item() == 0
    assert engine.combat.damage_ramp_stage[0, reused_slot].item() == 0
