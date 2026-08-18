from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.combat import StationaryCombatState, step_stationary_combat_
from clasher.torch_sim.oracle_event_capture import PythonOracleEventCapture
from clasher.torch_sim.resident_differential import _oracle_events, _resident_events
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _shield(entity: Troop) -> Any:
    return next(
        mechanic for mechanic in entity.mechanics if type(mechanic).__name__ == "Shield"
    )


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = battle._spawn_entity(Troop, position, player, stats)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    assert isinstance(entity, Troop)
    return entity


def _direct_battle(
    *, target_name: str = "Guards", target_hp: float | None = None
) -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn(battle, "Knight", 0, Position(9.0, 12.0))
    target = _spawn(battle, target_name, 1, Position(10.0, 12.0))
    attacker.target_id = target.id
    attacker.attack_cooldown = 0.0
    target.attack_cooldown = 10.0
    target.stun_timer = 100.0
    if target_hp is not None:
        target.hitpoints = target_hp
        target.max_hitpoints = target_hp
    return battle


def _set_hand(battle: BattleState, card: str, player: int = 0) -> None:
    state = battle.players[player]
    state.hand = [card, "Knight", "Cannon", "Zap"]
    state.deck = [name for name in state.hand if name is not None]
    state.cycle_queue = deque()
    state.elixir = 20.0


def _placement(engine: TensorResidentEngine, player: int = 0) -> int:
    state = engine.deployment.action_state(engine.runtime)
    legal = engine.deployment.kernel.legal_action_mask(state)
    options = torch.nonzero(legal[0, player, : 18 * 32], as_tuple=False)
    assert options.numel()
    return int(options[0, 0])


def _slot(engine: TensorResidentEngine, entity_id: int, row: int = 0) -> int:
    result = torch.nonzero(
        engine.runtime.battle.entity_id[row] == entity_id,
        as_tuple=False,
    ).flatten()
    assert result.numel() == 1
    return int(result.item())


def test_stationary_shield_hits_resolve_in_source_id_order_across_slot_permutations(
    tensor_device: str,
) -> None:
    def run(
        entity_ids: tuple[int, int, int, int],
    ) -> tuple[float, int, float, dict[int, tuple[bool, bool, float]]]:
        state = StationaryCombatState.empty(1, 4, device=tensor_device)
        state.present[0] = True
        state.alive[0] = True
        state.entity_id[0] = torch.tensor(entity_ids, device=state.device)
        state.owner[0] = torch.tensor(
            [0 if entity_id != 40 else 1 for entity_id in entity_ids],
            dtype=torch.int8,
            device=state.device,
        )
        state.x_units[0] = 9_000
        state.y_units[0] = 12_000
        state.hp[0] = 200.0
        state.max_hp[0] = 200.0
        state.damage[0] = 60.0
        state.range_units[0] = 1_000
        state.sight_range_units[0] = 5_500
        state.can_attack_ground[0] = True
        state.attack_cooldown[0] = 0.0
        target_slot = entity_ids.index(40)
        state.combat_enabled[0, target_slot] = False
        state.has_shield[0, target_slot] = True
        state.shield_hp[0, target_slot] = 100.0
        state.shield_integer_kind[0, target_slot] = True

        result = step_stationary_combat_(state)

        assert result.direct_hits is not None
        by_source: dict[int, tuple[bool, bool, float]] = {}
        for source_slot, entity_id in enumerate(entity_ids):
            if entity_id == 40:
                continue
            by_source[entity_id] = (
                bool(result.direct_hits.shield_absorbed[0, source_slot, 0].item()),
                bool(result.direct_hits.shield_broken[0, source_slot, 0].item()),
                float(result.direct_hits.applied[0, source_slot, 0].item()),
            )
        return (
            float(state.shield_hp[0, target_slot].item()),
            int(state.shield_break_count[0, target_slot].item()),
            float(state.hp[0, target_slot].item()),
            by_source,
        )

    expected = (
        0.0,
        1,
        140.0,
        {
            10: (True, False, 0.0),
            20: (True, True, 0.0),
            30: (False, False, 60.0),
        },
    )
    assert run((10, 20, 30, 40)) == expected
    assert run((40, 30, 10, 20)) == expected


def test_complete_direct_guards_lifecycle_matches_oracle(
    tensor_device: str,
) -> None:
    battle = _direct_battle()
    oracle = deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=tensor_device,
        max_entities=16,
        max_objects=16,
        event_capacity=128,
    )

    for tick in range(60):
        event_start = int(engine.runtime.events.count[0].item())
        with PythonOracleEventCapture(oracle) as capture:
            capture.step_logic_ticks(1)
        result = engine.step(player_order=torch.tensor([[0, 1]], device=engine.device))
        assert result.committed.tolist() == [True], tick
        assert _resident_events(engine, 0, event_start) == _oracle_events(
            capture.events, engine
        )
        assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
        resident_present = 2 in engine.runtime.battle.entity_id[0].tolist()
        assert resident_present is (2 in oracle.entities)
        if not resident_present:
            continue
        target_slot = _slot(engine, 2)
        oracle_target = oracle.entities[2]
        assert isinstance(oracle_target, Troop)
        oracle_shield = _shield(oracle_target)
        assert engine.mechanics.shield_current[0, target_slot].item() == float(
            oracle_shield.current_shield
        )
        assert engine.mechanics.shield_break_count[0, target_slot].item() == getattr(
            oracle_target, "_shield_break_count", 0
        )
        assert engine.shield_integer_kind[0, target_slot].item() is (
            type(oracle_shield.current_shield) is int
        )
        assert engine.runtime.battle.entity_hp[0, target_slot].item() == float(
            oracle_target.hitpoints
        )
        assert engine.runtime.battle.entity_hp_integer_kind[0, target_slot].item() is (
            type(oracle_target.hitpoints) is int
        )


def test_guards_action_materializes_exact_three_unit_formation(
    tensor_device: str,
) -> None:
    battle = BattleState(fast_path=False)
    _set_hand(battle, "Guards")
    oracle = battle.clone()
    first_id = battle.next_entity_id
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=tensor_device,
        max_entities=32,
        max_objects=16,
        event_capacity=256,
    )
    action = _placement(engine)
    actions = torch.tensor([[action, NO_OP_ACTION]], device=engine.device)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    with PythonOracleEventCapture(oracle) as capture:
        assert capture.command(lambda: action_space.apply_action(oracle, 0, action))
        capture.step_logic_ticks(1)

    preflight = engine.preflight(actions)
    result = engine.step(
        actions,
        player_order=torch.tensor([[0, 1]], device=engine.device),
    )

    assert preflight.supported.tolist() == [True]
    assert result.committed.tolist() == [True]
    assert _resident_events(engine, 0, 0) == _oracle_events(capture.events, engine)
    assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
    scalar = sorted(
        (
            entity_id,
            round(entity.position.x * 1_000),
            round(entity.position.y * 1_000),
            entity.deploy_delay_remaining,
            _shield(entity).current_shield,
        )
        for entity_id, entity in oracle.entities.items()
        if entity_id >= first_id and isinstance(entity, Troop)
    )
    resident = []
    for entity_id in range(first_id, first_id + 3):
        slot = _slot(engine, entity_id)
        resident.append(
            (
                entity_id,
                int(engine.runtime.battle.entity_x_units[0, slot].item()),
                int(engine.runtime.battle.entity_y_units[0, slot].item()),
                float(engine.runtime.battle.entity_deploy_delay[0, slot].item()),
                engine.mechanics.shield_current[0, slot].item(),
            )
        )
        assert engine.shield_integer_kind[0, slot].item()
    assert resident == scalar
    shield_owner = engine.mechanic_deployment.catalog.owner_index("shield")
    assert (
        engine.mechanic_deployment.state.owner_entity_id[shield_owner, 0] >= first_id
    ).sum().item() == 3


def test_dark_prince_and_nearby_projectile_rows_remain_fail_closed() -> None:
    safe = _direct_battle()
    dark_prince = _direct_battle(target_name="DarkPrince")

    projectile = _direct_battle()
    projectile.entities.pop(1)
    projectile.next_entity_id = 3
    source = _spawn(projectile, "Musketeer", 0, Position(9.0, 12.0))
    source.target_id = 2
    source.attack_cooldown = 0.0
    engine = TensorResidentEngine.from_battles(
        [safe, dark_prince, projectile],
        max_entities=16,
        max_objects=16,
        event_capacity=128,
    )
    before_time = engine.runtime.battle.time.clone()
    before_hp = engine.runtime.battle.entity_hp.clone()

    preflight = engine.preflight()
    result = engine.step()

    assert preflight.supported.tolist() == [True, False, False]
    assert result.committed.tolist() == [True, False, False]
    assert engine.runtime.battle.time.tolist() == [0.05, 0.0, 0.0]
    assert engine.mechanics.shield_current[0, 1].item() == 54.0
    assert torch.equal(engine.runtime.battle.time[1:], before_time[1:])
    assert torch.equal(engine.runtime.battle.entity_hp[1:], before_hp[1:])


def test_guards_action_commits_while_dark_prince_action_rolls_back() -> None:
    guards = BattleState(fast_path=False)
    dark_prince = BattleState(fast_path=False)
    _set_hand(guards, "Guards")
    _set_hand(dark_prince, "DarkPrince")
    engine = TensorResidentEngine.from_battles(
        [guards, dark_prince],
        max_entities=32,
        max_objects=16,
        event_capacity=256,
    )
    action = _placement(engine)
    actions = torch.tensor(
        [[action, NO_OP_ACTION], [action, NO_OP_ACTION]],
        device=engine.device,
    )
    before_ids = engine.runtime.battle.entity_id[1].clone()
    before_elixir = engine.runtime.battle.elixir[1].clone()
    before_hand = engine.runtime.battle.hand[1].clone()
    before_rng = engine.runtime.battle.rng.python_state(1)

    preflight = engine.preflight(actions)
    result = engine.step(
        actions,
        player_order=torch.tensor([[0, 1], [0, 1]]),
    )

    assert preflight.supported.tolist() == [True, False]
    assert result.committed.tolist() == [True, False]
    assert (
        engine.runtime.battle.entity_id[0] >= guards.next_entity_id
    ).sum().item() == 3
    assert torch.equal(engine.runtime.battle.entity_id[1], before_ids)
    assert torch.equal(engine.runtime.battle.elixir[1], before_elixir)
    assert torch.equal(engine.runtime.battle.hand[1], before_hand)
    assert engine.runtime.battle.rng.python_state(1) == before_rng


def test_direct_damage_event_capacity_failure_rolls_back_shield_row() -> None:
    battle = _direct_battle()
    shield = _shield(battle.entities[2])
    shield.current_shield = 0.0
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=8, event_capacity=1
    )
    engine.runtime.events.count.fill_(1)
    before_hp = engine.runtime.battle.entity_hp.clone()
    before_shield = engine.mechanics.shield_current.clone()
    before_time = engine.runtime.battle.time.clone()

    result = engine.step()

    assert result.committed.tolist() == [False]
    assert torch.equal(engine.runtime.battle.entity_hp, before_hp)
    assert torch.equal(engine.mechanics.shield_current, before_shield)
    assert torch.equal(engine.runtime.battle.time, before_time)
    assert engine.runtime.events.count.tolist() == [1]


def test_shield_workspace_and_cleanup_slot_reuse_reset_identity() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn(battle, "Knight", 1, Position(9.0, 12.0))
    target = _spawn(battle, "Guards", 0, Position(10.0, 12.0))
    attacker.target_id = target.id
    attacker.attack_cooldown = 0.0
    target.hitpoints = 1.0
    _shield(target).current_shield = 0.0
    _set_hand(battle, "Guards")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=16, event_capacity=128
    )
    workspace = TensorResidentWorkspace(engine)
    assert workspace.scratch.shield_catalog is engine.shield_catalog
    assert workspace.scratch.shield_integer_kind.data_ptr() != (
        engine.shield_integer_kind.data_ptr()
    )

    killed = workspace.step()
    assert killed.committed.tolist() == [True]
    assert 2 not in engine.runtime.battle.entity_id[0].tolist()
    shield_owner = engine.mechanic_deployment.catalog.owner_index("shield")
    assert not (
        engine.mechanic_deployment.state.owner_entity_id[shield_owner, 0] == 2
    ).any()
    action = _placement(engine)
    deployed = workspace.step(
        torch.tensor([[action, NO_OP_ACTION]]),
        player_order=torch.tensor([[0, 1]]),
    )
    assert deployed.committed.tolist() == [True]
    reused_slot = _slot(engine, 3)
    assert reused_slot == 1
    assert engine.mechanics.shield_break_count[0, reused_slot].item() == 0
    assert engine.mechanics.shield_current[0, reused_slot].item() > 0.0
    assert engine.shield_integer_kind[0, reused_slot].item()
    workspace.scratch.shield_integer_kind.zero_()
    workspace.refresh()
    assert torch.equal(
        workspace.scratch.shield_integer_kind,
        engine.shield_integer_kind,
    )
