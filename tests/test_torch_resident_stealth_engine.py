from __future__ import annotations

import copy
import random
from collections import deque
from typing import Any, cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.diagnostics import first_divergence
from clasher.torch_sim.resident_differential import (
    _oracle_snapshot,
    _resident_snapshot,
)
from clasher.torch_sim.resident_engine import (
    ResidentUnsupportedReason,
    TensorResidentEngine,
)
from clasher.torch_sim.resident_outputs import ResidentOutputProjector
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _spawn(
    battle: BattleState,
    entity_type: type[Troop | Building],
    name: str,
    player: int,
    position: Position,
) -> Troop | Building:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = battle._spawn_entity(entity_type, position, player, stats)
    assert isinstance(entity, (Troop, Building))
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _engine(battles: list[BattleState], device: str) -> TensorResidentEngine:
    return TensorResidentEngine.from_battles(
        battles,
        device=device,
        max_entities=24,
        max_objects=16,
        event_capacity=512,
    )


def _slot(engine: TensorResidentEngine, entity_id: int, row: int = 0) -> int:
    values = torch.nonzero(
        engine.runtime.battle.entity_id[row] == entity_id, as_tuple=False
    ).flatten()
    assert values.numel() == 1
    return int(values.item())


def _assert_tick(
    engine: TensorResidentEngine,
    oracle: BattleState,
    *,
    workspace: TensorResidentWorkspace | None = None,
    actions: torch.Tensor | None = None,
) -> Any:
    oracle.step_logic_ticks(1)
    order = torch.tensor([[0, 1]], device=engine.device)
    result = (
        engine.step(actions, player_order=order)
        if workspace is None
        else workspace.step(actions, player_order=order)
    )
    assert result.committed.tolist() == [True], engine.diagnose_preflight(actions)
    divergence = first_divergence(
        _oracle_snapshot(oracle),
        _resident_snapshot(engine, 0),
    )
    assert divergence is None, divergence
    assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
    return result


def _ghost_melee(*, ghost_first: bool) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(8_242_001))
    battle.entities.clear()
    battle.next_entity_id = 1
    order = (
        (
            (Troop, "RoyalGhost", 0, Position(9.0, 12.0)),
            (Troop, "Knight", 1, Position(9.0, 13.0)),
        )
        if ghost_first
        else (
            (Troop, "Knight", 1, Position(9.0, 13.0)),
            (Troop, "RoyalGhost", 0, Position(9.0, 12.0)),
        )
    )
    left = _spawn(battle, *order[0])
    right = _spawn(battle, *order[1])
    ghost = (
        left
        if any(
            type(mechanic).__name__ == "InvisibilityWhenNotAttacking"
            for mechanic in left.mechanics
        )
        else right
    )
    knight = right if ghost is left else left
    ghost.target_id = knight.id
    knight.target_id = ghost.id
    ghost.attack_cooldown = 0.0
    knight.attack_cooldown = 0.0
    return battle


@pytest.mark.parametrize("ghost_first", (True, False))
def test_ghost_reveal_occurs_inside_stable_combat_order(
    tensor_device: str,
    ghost_first: bool,
) -> None:
    boundary = _ghost_melee(ghost_first=ghost_first)
    oracle = copy.deepcopy(boundary)
    engine = _engine([boundary], tensor_device)
    ghost_id = next(
        entity.id
        for entity in boundary.entities.values()
        if any(
            type(mechanic).__name__ == "InvisibilityWhenNotAttacking"
            for mechanic in entity.mechanics
        )
    )
    knight_id = next(
        entity.id
        for entity in boundary.entities.values()
        if entity.card_stats.name == "Knight"
    )

    result = _assert_tick(engine, oracle)

    ghost_slot = _slot(engine, ghost_id)
    knight_slot = _slot(engine, knight_id)
    assert result.combat.attacked[0, ghost_slot]
    assert bool(result.combat.attacked[0, knight_slot]) is ghost_first
    assert engine.stealth.state.stealth_until_ms[0, ghost_slot].item() == 0
    assert result.stealth.targetable[0, ghost_slot]


def test_invisible_ghost_remains_direct_area_secondary_eligible(
    tensor_device: str,
) -> None:
    battle = BattleState(fast_path=False, rng=random.Random(8_242_002))
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn(battle, Troop, "RoyalGhost", 0, Position(9.0, 12.0))
    primary = _spawn(battle, Troop, "Knight", 1, Position(9.0, 13.0))
    secondary = _spawn(battle, Troop, "RoyalGhost", 1, Position(9.4, 13.0))
    source.target_id = primary.id
    source.attack_cooldown = 0.0
    primary.stun_timer = 100.0
    secondary.stun_timer = 100.0
    oracle = copy.deepcopy(battle)
    engine = _engine([battle], tensor_device)

    result = _assert_tick(engine, oracle)

    secondary_slot = _slot(engine, secondary.id)
    assert result.combat.damage_received[0, secondary_slot] > 0
    assert result.stealth.secondary_targetable[0, secondary_slot]
    assert result.stealth.area_receivable[0, secondary_slot]
    assert not result.stealth.targetable[0, secondary_slot]


def test_fade_preserves_enemy_lock_until_next_combat_validation(
    tensor_device: str,
) -> None:
    battle = BattleState(fast_path=False, rng=random.Random(8_242_003))
    battle.entities.clear()
    battle.next_entity_id = 1
    enemy = _spawn(battle, Troop, "Knight", 1, Position(9.0, 25.0))
    ghost = _spawn(battle, Troop, "RoyalGhost", 0, Position(9.0, 12.0))
    fade = next(
        mechanic
        for mechanic in ghost.mechanics
        if type(mechanic).__name__ == "InvisibilityWhenNotAttacking"
    )
    fade_state = cast(Any, fade)
    fade_state.time_since_attack_ms = float(fade_state.fade_delay_ms - 50)
    cast(Any, ghost)._stealth_until = 0
    enemy.target_id = ghost.id
    enemy.stun_timer = 100.0
    ghost.stun_timer = 100.0
    oracle = copy.deepcopy(battle)
    engine = _engine([battle], tensor_device)
    projection = ResidentOutputProjector.from_engine(
        engine,
        [battle],
        structured_builder=StructuredObservationBuilder(card_vocab=[], max_entities=24),
        cv_builder=CvObservationBuilder(card_vocab=[]),
    )
    enemy_slot = _slot(engine, enemy.id)
    ghost_slot = _slot(engine, ghost.id)

    faded = _assert_tick(engine, oracle)
    projection.project_structured()
    assert faded.stealth.invisible[0, ghost_slot]
    assert projection.observations.entity_stealth_until_ms[0, ghost_slot].item() == (
        engine.stealth.state.stealth_until_ms[0, ghost_slot].item()
    )
    assert engine.combat_target_entity_id[0, enemy_slot].item() == ghost.id
    assert oracle.entities[enemy.id].target_id == ghost.id

    _assert_tick(engine, oracle)
    assert engine.combat_target_entity_id[0, enemy_slot].item() == -1
    assert oracle.entities[enemy.id].target_id is None


def test_tesla_hidden_cycle_blocks_combat_not_collision_and_reveals(
    tensor_device: str,
) -> None:
    battle = BattleState(fast_path=False, rng=random.Random(8_242_004))
    battle.entities.clear()
    battle.next_entity_id = 1
    tesla = _spawn(battle, Building, "Tesla", 0, Position(9.0, 12.0))
    target = _spawn(battle, Troop, "Knight", 1, Position(9.0, 25.0))
    target.stun_timer = 100.0
    hide = next(
        mechanic
        for mechanic in tesla.mechanics
        if type(mechanic).__name__ == "HideWhenIdle"
    )
    hide_state = cast(Any, hide)
    hide_state._phase_ms = float(hide_state.hide_delay_ms - 50)
    cast(Any, tesla)._hidden_building = False
    cast(Any, tesla)._special_move_active = False
    oracle = copy.deepcopy(battle)
    engine = _engine([battle], tensor_device)
    projection = ResidentOutputProjector.from_engine(
        engine,
        [battle],
        structured_builder=StructuredObservationBuilder(card_vocab=[], max_entities=24),
        cv_builder=CvObservationBuilder(card_vocab=[]),
    )
    tesla_slot = _slot(engine, tesla.id)
    target_slot = _slot(engine, target.id)

    hidden = _assert_tick(engine, oracle)
    projection.project_structured()
    assert hidden.stealth.hidden_building[0, tesla_slot]
    assert projection.observations.entity_hidden_building[0, tesla_slot]
    assert hidden.stealth.combat_blocked[0, tesla_slot]
    assert hidden.stealth.movement_blocked[0, tesla_slot]
    assert engine.movement.slot_present[0, tesla_slot]
    assert engine.movement.collision_radius_units[0, tesla_slot] > 0

    oracle.entities[target.id].position = Position(9.0, 13.0)
    engine.runtime.battle.entity_y_units[0, target_slot] = 13_000
    revealed = _assert_tick(engine, oracle)
    projection.project_structured()
    assert not revealed.stealth.hidden_building[0, tesla_slot]
    assert not projection.observations.entity_hidden_building[0, tesla_slot]
    assert revealed.stealth.targetable[0, tesla_slot]


@pytest.mark.parametrize("card_name", ("RoyalGhost", "Tesla"))
def test_stealth_action_initializes_one_owner_and_exact_first_tick(
    tensor_device: str,
    card_name: str,
) -> None:
    battle = BattleState(fast_path=False, rng=random.Random(8_242_005))
    player = battle.players[0]
    player.hand = [card_name, "Knight", "Cannon", "Zap"]
    player.deck = [card for card in player.hand if card is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0
    oracle = copy.deepcopy(battle)
    engine = _engine([battle], tensor_device)
    state = engine.deployment.action_state(engine.runtime)
    legal = engine.deployment.kernel.legal_action_mask(state)
    action = int(torch.nonzero(legal[0, 0, : 18 * 32], as_tuple=False)[0, 0])
    actions = torch.tensor([[action, NO_OP_ACTION]], device=engine.device)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    assert action_space.apply_action(oracle, 0, action)

    result = _assert_tick(engine, oracle, actions=actions)

    owner = engine.mechanic_deployment.catalog.owner_index("stealth")
    owner_ids = engine.mechanic_deployment.state.owner_entity_id[owner, 0]
    assert (owner_ids > 0).sum().item() == 1
    spawned_id = int(owner_ids.max().item())
    spawned_slot = _slot(engine, spawned_id)
    assert engine.stealth.state.entity_id[0, spawned_slot].item() == spawned_id
    if card_name == "RoyalGhost":
        assert result.stealth.invisible[0, spawned_slot]
    else:
        assert not result.stealth.hidden_building[0, spawned_slot]


def test_stealth_conflicts_fail_closed_and_workspace_rolls_back() -> None:
    clean = _ghost_melee(ghost_first=True)
    conflict = _ghost_melee(ghost_first=True)
    musketeer = _spawn(
        conflict,
        Troop,
        "Musketeer",
        0,
        Position(3.0, 10.0),
    )
    musketeer.stun_timer = 100.0
    engine = _engine([clean, conflict], "cpu")
    workspace = TensorResidentWorkspace(engine)
    before_runtime = engine.runtime.battle.entity_id[1].clone()
    before_stealth = engine.stealth.state.clone()

    preflight = engine.preflight()
    result = workspace.step()

    assert preflight.supported.tolist() == [True, False]
    assert preflight.reason_code.tolist()[1] == int(
        ResidentUnsupportedReason.ACTIVE_MECHANIC
    )
    assert result.committed.tolist() == [True, False]
    assert torch.equal(engine.runtime.battle.entity_id[1], before_runtime)
    for name in before_stealth.__dataclass_fields__:
        assert torch.equal(
            getattr(engine.stealth.state, name)[1],
            getattr(before_stealth, name)[1],
        )


def test_stealth_slot_reuse_reinitializes_identity_and_visibility() -> None:
    battle = _ghost_melee(ghost_first=True)
    player = battle.players[0]
    player.hand = ["RoyalGhost", "Knight", "Cannon", "Zap"]
    player.deck = [card for card in player.hand if card is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0
    ghost_id = next(
        entity.id
        for entity in battle.entities.values()
        if any(
            type(mechanic).__name__ == "InvisibilityWhenNotAttacking"
            for mechanic in entity.mechanics
        )
    )
    engine = _engine([battle], "cpu")
    old_slot = _slot(engine, ghost_id)
    engine.runtime.battle.entity_hp[0, old_slot] = 0.0
    engine.runtime.battle.entity_active[0, old_slot] = False
    engine.combat.hp[0, old_slot] = 0.0
    engine.combat.alive[0, old_slot] = False
    assert engine.step().committed.tolist() == [True]
    assert engine.stealth.state.entity_id[0, old_slot].item() == 0

    state = engine.deployment.action_state(engine.runtime)
    legal = engine.deployment.kernel.legal_action_mask(state)
    action = int(torch.nonzero(legal[0, 0, : 18 * 32], as_tuple=False)[0, 0])
    result = engine.step(torch.tensor([[action, NO_OP_ACTION]]))

    assert result.committed.tolist() == [True]
    new_id = int(engine.runtime.battle.entity_id[0, old_slot].item())
    assert new_id > ghost_id
    assert engine.stealth.state.entity_id[0, old_slot].item() == new_id
    assert result.stealth.invisible[0, old_slot]


def test_combat_projectile_allocation_refreshes_stealth_object_identity(
    tensor_device: str,
) -> None:
    battle = BattleState(fast_path=False, rng=random.Random(8_242_006))
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn(battle, Troop, "BabyDragon", 0, Position(9.0, 10.0))
    target = _spawn(battle, Troop, "Knight", 1, Position(9.0, 13.0))
    source.target_id = target.id
    target.target_id = source.id
    source.attack_cooldown = 0.0
    source.last_attack_time = -10.0
    target.speed = 0.0
    target.damage = 0.0
    target.attack_cooldown = 10.0
    target.stun_timer = 100.0
    engine = _engine([battle], tensor_device)

    result = engine.step(player_order=torch.tensor([[0, 1]], device=engine.device))

    assert result.committed.tolist() == [True]
    object_slots = torch.where(engine.runtime.battle.entity_kind[0] == 2)[0]
    assert object_slots.numel() == 1
    object_slot = int(object_slots.item())
    object_id = int(engine.runtime.battle.entity_id[0, object_slot].item())
    assert engine.stealth.target_entity_id[0, object_slot].item() == object_id
    assert engine.stealth.state.entity_id[0, object_slot].item() == object_id
