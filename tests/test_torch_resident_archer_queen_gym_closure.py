from __future__ import annotations

from collections import deque

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.torch_sim.actions import ABILITY_ACTION, NO_OP_ACTION
from clasher.torch_sim.resident_archer_queen import (
    TensorArcherQueenState,
    step_archer_queen_,
)
from clasher.torch_sim.resident_champion_actions import (
    champion_player_legality,
    publish_champion_legality_,
    route_champion_commands_,
)
from clasher.torch_sim.resident_engine import TensorResidentEngine

DEPLOY_QUEEN = 10 * 18 + 8


def _battle(*, deploy_delay: float = 0.0) -> tuple[BattleState, int, int]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    battle._champion_ability_owner_ids.clear()
    for player in battle.players:
        player.hand = ["Knight", "Archers", "Skeletons", "Zap"]
        player.deck = [name for name in player.hand if name is not None]
        player.cycle_queue = deque(["Cannon"])
        player.elixir = 10.0
    queen_stats = battle.card_loader.get_card("ArcherQueen")
    knight_stats = battle.card_loader.get_card("Knight")
    assert queen_stats is not None and knight_stats is not None
    queen = battle._spawn_entity(Troop, Position(8.0, 12.0), 0, queen_stats)
    target = battle._spawn_entity(Troop, Position(12.0, 12.0), 1, knight_stats)
    for entity in (queen, target):
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    queen.deploy_delay_remaining = deploy_delay
    target.deploy_delay_remaining = 0.0
    return battle, queen.id, target.id


def _engine(battle: BattleState) -> TensorResidentEngine:
    return TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=8, event_capacity=512
    )


def _slot(engine: TensorResidentEngine, entity_id: int) -> int:
    matches = torch.nonzero(
        engine.runtime.battle.entity_id[0] == entity_id, as_tuple=False
    ).flatten()
    assert matches.numel() == 1
    return int(matches.item())


def test_policy_button_is_published_only_after_deployment_finishes() -> None:
    battle, queen_id, _ = _battle(deploy_delay=1.0)
    engine = _engine(battle)
    queen_slot = _slot(engine, queen_id)

    action_state = engine.deployment.action_state(engine.runtime)
    assert not champion_player_legality(engine.mechanics, engine.runtime).any()
    assert not publish_champion_legality_(
        action_state, engine.mechanics, engine.runtime
    ).any()
    assert not engine.deployment.kernel.legal_action_mask(action_state)[
        0, 0, ABILITY_ACTION
    ]

    engine.runtime.battle.entity_deploy_delay[0, queen_slot] = 0.0
    engine.runtime.battle.entity_placement_pending[0, queen_slot] = True
    assert not publish_champion_legality_(
        action_state, engine.mechanics, engine.runtime
    ).any()
    engine.runtime.battle.entity_placement_pending[0, queen_slot] = False
    assert publish_champion_legality_(
        action_state, engine.mechanics, engine.runtime
    ).tolist() == [[True, False]]
    assert engine.deployment.kernel.legal_action_mask(action_state)[
        0, 0, ABILITY_ACTION
    ]
    engine.runtime.battle.elixir[0, 0] = 0.0
    assert not publish_champion_legality_(
        action_state, engine.mechanics, engine.runtime
    ).any()


def test_ability_command_spends_mechanic_cost_without_rotating_cards() -> None:
    battle, queen_id, _ = _battle()
    engine = _engine(battle)
    queen_slot = _slot(engine, queen_id)
    action_state = engine.deployment.action_state(engine.runtime)
    publish_champion_legality_(action_state, engine.mechanics, engine.runtime)
    legal = engine.deployment.kernel.legal_action_mask(action_state)
    before_hand = action_state.hand_ids.clone()
    before_cycle = action_state.cycle_ids.clone()

    ingress = engine.deployment.kernel.ingress(
        action_state,
        torch.tensor([[ABILITY_ACTION, NO_OP_ACTION]]),
        legal_mask=legal,
    )
    result = route_champion_commands_(
        engine.mechanics, engine.runtime, ingress.commands
    )

    assert ingress.accepted.tolist() == [[True, True]]
    assert result.command_success.tolist() == [True]
    assert result.activation is not None
    assert result.activation.activated[0, queen_slot]
    assert engine.runtime.battle.elixir.tolist() == [[9.0, 10.0]]
    assert torch.equal(ingress.hand_ids, before_hand)
    assert torch.equal(ingress.cycle_ids, before_cycle)
    assert not champion_player_legality(engine.mechanics, engine.runtime).any()
    assert engine.mechanics.cloak_pending_until_ms[0, queen_slot].item() == 200
    assert engine.mechanics.cast_lock_until_ms[0, queen_slot].item() == 933


def test_cloak_visibility_attack_rate_projectile_and_cooldown_are_policy_stable() -> None:
    battle, queen_id, target_id = _battle()
    engine = _engine(battle)
    queen_slot = _slot(engine, queen_id)
    target_slot = _slot(engine, target_id)
    action_state = engine.deployment.action_state(engine.runtime)
    publish_champion_legality_(action_state, engine.mechanics, engine.runtime)
    ingress = engine.deployment.kernel.ingress(
        action_state,
        torch.tensor([[ABILITY_ACTION, NO_OP_ACTION]]),
    )
    route_champion_commands_(engine.mechanics, engine.runtime, ingress.commands)

    owner = TensorArcherQueenState.from_battles(engine.runtime, [battle])
    # Reuse the already-activated generalized mechanic planes instead of
    # reconstructing mutable ability state from the Python adapter.
    owner.mechanics = engine.mechanics
    for _ in range(4):
        result = step_archer_queen_(owner, engine.runtime)
        assert result.committed.item()

    assert engine.runtime.battle.time.item() == pytest.approx(0.2)
    assert owner.mechanics.hidden_from_enemies(engine.runtime)[0, queen_slot]
    assert owner.mechanics.attack_rate_multiplier(engine.runtime)[
        0, queen_slot
    ].item() == pytest.approx(2.8)
    assert not owner.combat.targetable[0, queen_slot]

    saw_projectile = False
    for _ in range(30):
        result = step_archer_queen_(owner, engine.runtime)
        assert result.committed.item()
        saw_projectile |= bool(owner.projectile_active.any().item())
        if saw_projectile:
            active = owner.projectile_active[0]
            assert owner.projectile_source_id[0, active].tolist() == [queen_id]
            assert owner.projectile_target_id[0, active].tolist() == [target_id]
            runtime_slot = owner.projectile_runtime_slot[0, active]
            assert engine.runtime.battle.entity_kind[0, runtime_slot].tolist() == [2]
            break
    assert saw_projectile
    assert engine.runtime.battle.entity_hp[0, target_slot] > 0.0

    engine.runtime.battle.time[0] = 20.699
    owner.mechanics.tick_cloak_(engine.runtime)
    assert not champion_player_legality(owner.mechanics, engine.runtime).any()
    engine.runtime.battle.time[0] = 20.700
    owner.mechanics.tick_cloak_(engine.runtime)
    assert champion_player_legality(owner.mechanics, engine.runtime).tolist() == [
        [True, False]
    ]


def test_full_engine_deploy_ability_and_projectile_lifecycle_has_zero_fallback() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    target_stats = battle.card_loader.get_card("Knight")
    assert target_stats is not None
    target = battle._spawn_entity(
        Troop,
        Position(8.5, 14.0),
        1,
        target_stats,
    )
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    target.attack_cooldown = 100.0
    player = battle.players[0]
    player.hand = ["ArcherQueen", "Knight", "Skeletons", "Zap"]
    player.deck = [name for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 10.0
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=24, max_objects=24, event_capacity=2_048
    )
    no_op = torch.tensor([[NO_OP_ACTION, NO_OP_ACTION]])

    assert engine.legal_action_mask()[0, 0, DEPLOY_QUEEN]
    deployed = engine.step(
        torch.tensor([[DEPLOY_QUEEN, NO_OP_ACTION]]),
        player_order=torch.tensor([[0, 1]]),
    )
    assert deployed.preflight.supported.tolist() == [True]
    assert deployed.committed.tolist() == [True]
    assert deployed.action_router.action_success.tolist() == [[True, True]]
    queen_core = engine.runtime.battle.card_to_id["ArcherQueen"]
    queen_mask = (
        engine.runtime.entity_pool.active
        & (engine.runtime.battle.entity_card == queen_core)
    )
    assert queen_mask.sum().item() == 1
    queen_slot = int(torch.nonzero(queen_mask[0], as_tuple=False).item())
    queen_id = int(engine.runtime.battle.entity_id[0, queen_slot].item())

    # Deployment admission and initialization were exercised above. Finish
    # the pre-play clock directly so this policy-lifecycle test stays focused
    # and fast rather than spending twenty full engine transactions waiting.
    engine.runtime.battle.entity_deploy_delay[0, queen_slot] = 0.0
    engine.runtime.battle.entity_placement_pending[0, queen_slot] = False

    for _ in range(30):
        if bool(engine.legal_action_mask()[0, 0, ABILITY_ACTION].item()):
            break
        waiting = engine.step(no_op)
        assert waiting.preflight.supported.tolist() == [True]
        assert waiting.committed.tolist() == [True]
    else:
        pytest.fail("deployed Champion ability did not become legal")

    before_elixir = float(engine.runtime.battle.elixir[0, 0].item())
    activated = engine.step(
        torch.tensor([[ABILITY_ACTION, NO_OP_ACTION]]),
        player_order=torch.tensor([[0, 1]]),
    )
    assert activated.preflight.supported.tolist() == [True]
    assert activated.committed.tolist() == [True]
    assert activated.action_router.action_success.tolist() == [[True, True]]
    assert engine.runtime.battle.elixir[0, 0].item() == pytest.approx(
        before_elixir - 1.0 + 0.05 / 2.8
    )
    assert engine.mechanics.ability_active[0, queen_slot]
    assert not engine.legal_action_mask()[0, 0, ABILITY_ACTION]

    saw_hidden = False
    saw_projectile = False
    for _ in range(80):
        tick = engine.step(no_op)
        assert tick.preflight.supported.tolist() == [True]
        assert tick.committed.tolist() == [True]
        hidden_now = bool(
            engine.mechanics.hidden_from_enemies(engine.runtime)[0, queen_slot].item()
        )
        saw_hidden |= hidden_now
        if hidden_now:
            assert engine.mechanics.attack_rate_multiplier(engine.runtime)[
                0, queen_slot
            ].item() == pytest.approx(2.8)
        allocated = engine.objects.objects.allocated[0]
        source_matches = (
            engine.projectile_source_entity_id[0] == queen_id
        ) & allocated
        launched_now = bool(tick.combat.projectile_launched.any().item())
        saw_projectile |= launched_now | bool(source_matches.any().item())
        if bool(source_matches.any().item()):
            assert engine.objects.objects.object_id[0, source_matches].gt(0).all()
        if saw_hidden and saw_projectile:
            break

    assert saw_hidden and saw_projectile
    assert engine.runtime.supported.tolist() == [True]
