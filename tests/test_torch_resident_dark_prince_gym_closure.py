from __future__ import annotations

from collections import deque
from typing import Any, cast

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.combat import StationaryCombatState, step_stationary_combat_
from clasher.torch_sim.movement import advance_native_charge_progress
from clasher.torch_sim.resident_engine import TensorResidentEngine


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = cast(Troop, battle._spawn_entity(Troop, position, player, stats))
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _shield(entity: Troop) -> Any:
    return next(
        mechanic for mechanic in entity.mechanics if type(mechanic).__name__ == "Shield"
    )


def _slot(engine: TensorResidentEngine, entity_id: int) -> int:
    slots = torch.nonzero(
        engine.runtime.battle.entity_id[0] == entity_id,
        as_tuple=False,
    ).flatten()
    assert slots.numel() == 1
    return int(slots.item())


def test_dark_prince_is_a_composition_of_existing_data_capabilities() -> None:
    battle = BattleState(fast_path=False)
    definition = battle.card_loader.load_card_definitions()["DarkPrince"]
    stats = battle.card_loader.get_card("DarkPrince")

    assert stats is not None
    assert tuple(type(item).__name__ for item in definition.mechanics) == ("Shield",)
    assert definition.effects == ()
    assert stats.charge_range == 300
    assert stats.charge_speed_multiplier == 200
    assert stats.scaled_damage_special == 532
    assert stats.area_damage_radius == 1_100


def test_charged_area_hit_and_whole_hit_shield_use_generic_kernels() -> None:
    # A 60-unit Dark Prince movement call contributes 200 charge points. The
    # crossing call arms charge; the following call observes it fully loaded.
    crossing = advance_native_charge_progress(
        torch.tensor([9_800]),
        torch.tensor([60]),
        torch.tensor([300]),
        active=torch.tensor([True]),
    )
    assert crossing.progress.tolist() == [10_000]
    assert crossing.charging.tolist() == [True]
    assert crossing.fully_loaded.tolist() == [False]

    loaded = advance_native_charge_progress(
        crossing.progress,
        torch.tensor([120]),
        torch.tensor([300]),
        active=torch.tensor([True]),
    )
    assert loaded.progress.tolist() == [10_000]
    assert loaded.charging.tolist() == [True]
    assert loaded.fully_loaded.tolist() == [True]

    # The stationary kernel already has the production-plausible interaction
    # we need: one charged scalar damage value, direct area recipients, and a
    # whole-hit shield. No DarkPrince identity branch is required.
    state = StationaryCombatState.empty(1, 3)
    state.present[0] = True
    state.alive[0] = True
    state.entity_id[0] = torch.tensor([1, 2, 3])
    state.owner[0] = torch.tensor([0, 1, 1], dtype=torch.int8)
    state.x_units[0] = torch.tensor([9_000, 10_000, 10_800])
    state.y_units[0] = 12_000
    state.collision_radius_units[0] = torch.tensor([600, 600, 500])
    state.hp[0] = torch.tensor([1_200.0, 1_000.0, 1_000.0])
    state.max_hp.copy_(state.hp)
    state.damage[0, 0] = 532.0
    state.range_units[0, 0] = 1_200
    state.sight_range_units[0, 0] = 5_500
    state.area_radius_units[0, 0] = 1_100
    state.can_attack_ground[0, 0] = True
    state.combat_enabled[0, 1:] = False
    state.attack_cooldown[0, 0] = 0.0
    state.attack_cooldown[0, 1:] = 10.0
    state.has_shield[0, 1] = True
    state.shield_hp[0, 1] = 300.0

    result = step_stationary_combat_(state)

    assert result.attacked.tolist() == [[True, False, False]]
    assert state.shield_hp[0, 1].item() == 0.0
    assert state.hp[0, 1].item() == 1_000.0
    assert state.hp[0, 2].item() == 468.0
    assert result.direct_hits is not None
    assert result.direct_hits.shield_absorbed[0, 0, 0].item()
    assert result.direct_hits.shield_broken[0, 0, 0].item()
    assert result.direct_hits.applied[0, 0, :2].tolist() == [0.0, 532.0]


def test_dark_prince_action_is_admitted_without_fallback() -> None:
    battle = BattleState(fast_path=False)
    state = battle.players[0]
    state.hand = ["DarkPrince", "Knight", "Cannon", "Zap"]
    state.deck = [name for name in state.hand if name is not None]
    state.cycle_queue = deque()
    state.elixir = 10.0
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=32, max_objects=16, event_capacity=128
    )
    card_id = engine.runtime.catalog.name_to_id["DarkPrince"]
    assert engine.shield_catalog.supported[card_id].item()
    assert engine.area_radius_units[card_id].item() == 1_100
    assert engine.charge_special_damage[card_id].item() == 532.0
    assert engine.charge_speed_percent[card_id].item() == 200

    legal = engine.deployment.kernel.legal_action_mask(
        engine.deployment.action_state(engine.runtime)
    )
    placements = torch.nonzero(legal[0, 0, : 18 * 32], as_tuple=False).flatten()
    assert placements.numel()
    actions = torch.tensor([[int(placements[0].item()), NO_OP_ACTION]])

    assert engine.preflight(actions).supported.tolist() == [True]
    result = engine.step(actions, player_order=torch.tensor([[0, 1]]))

    assert result.committed.tolist() == [True]
    allocation = result.deployment.deployment.allocation
    assert allocation.valid[0].sum().item() == 1
    spawned_slot = int(allocation.slots[0][allocation.valid[0]][0].item())
    assert engine.mechanics.shield_current[0, spawned_slot].item() > 0.0
    assert engine.movement.charge_component[0, spawned_slot].item()


def test_charged_dark_prince_hit_updates_policy_state_without_fallback() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn(battle, "DarkPrince", 0, Position(9.0, 12.0))
    primary = _spawn(battle, "Guards", 1, Position(10.0, 12.0))
    secondary = _spawn(battle, "Knight", 1, Position(10.8, 12.0))
    attacker.target_id = primary.id
    attacker.attack_cooldown = 0.0
    attacker._native_charge_progress = 10_000
    attacker.is_charging = True
    attacker._native_natural_movement_active = True
    for target in (primary, secondary):
        target.attack_cooldown = 10.0
        target.stun_timer = 100.0
    oracle = battle.clone()
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=16, event_capacity=128
    )

    assert engine.preflight().supported.tolist() == [True]
    oracle._step_logic_tick()
    result = engine.step(player_order=torch.tensor([[0, 1]]))

    assert result.committed.tolist() == [True]
    for entity_id in (attacker.id, primary.id, secondary.id):
        oracle_entity = cast(Troop, oracle.entities[entity_id])
        slot = _slot(engine, entity_id)
        assert engine.runtime.battle.entity_hp[0, slot].item() == float(
            oracle_entity.hitpoints
        )
        assert engine.runtime.battle.entity_x_units[0, slot].item() == round(
            oracle_entity.position.x * 1_000
        )
        assert engine.runtime.battle.entity_y_units[0, slot].item() == round(
            oracle_entity.position.y * 1_000
        )
    primary_slot = _slot(engine, primary.id)
    oracle_primary = cast(Troop, oracle.entities[primary.id])
    assert engine.mechanics.shield_current[0, primary_slot].item() == float(
        _shield(oracle_primary).current_shield
    )
    attacker_slot = _slot(engine, attacker.id)
    assert engine.movement.native_charge_progress[0, attacker_slot].item() == 0
    assert engine.movement.effective_speed_units[0, attacker_slot].item() == 60


def test_charge_threshold_crossing_arms_on_the_following_movement_call() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn(battle, "DarkPrince", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Giant", 1, Position(9.0, 24.0))
    attacker.target_id = target.id
    attacker.attack_cooldown = 0.8
    attacker._native_charge_progress = 9_800
    attacker._native_natural_movement_active = True
    target.attack_cooldown = 10.0
    target.stun_timer = 100.0
    oracle = battle.clone()
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=16, event_capacity=128
    )
    attacker_slot = _slot(engine, attacker.id)

    oracle._step_logic_tick()
    first = engine.step(player_order=torch.tensor([[0, 1]]))
    assert first.committed.tolist() == [True]
    oracle_attacker = cast(Troop, oracle.entities[attacker.id])
    assert oracle_attacker._native_charge_progress == 10_000
    assert engine.movement.native_charge_progress[0, attacker_slot].item() == 10_000
    assert oracle_attacker.attack_cooldown > 0.0
    assert engine.combat.attack_cooldown[0, attacker_slot].item() == (
        oracle_attacker.attack_cooldown
    )
    assert engine.movement.effective_speed_units[0, attacker_slot].item() == 60

    oracle._step_logic_tick()
    second = engine.step(player_order=torch.tensor([[0, 1]]))
    assert second.committed.tolist() == [True]
    oracle_attacker = cast(Troop, oracle.entities[attacker.id])
    assert oracle_attacker.attack_cooldown == 0.0
    assert engine.combat.attack_cooldown[0, attacker_slot].item() == 0.0
    assert engine.movement.native_charge_progress[0, attacker_slot].item() == 10_000
    assert engine.movement.effective_speed_units[0, attacker_slot].item() == 120
    assert engine.runtime.battle.entity_x_units[0, attacker_slot].item() == round(
        oracle_attacker.position.x * 1_000
    )
    assert engine.runtime.battle.entity_y_units[0, attacker_slot].item() == round(
        oracle_attacker.position.y * 1_000
    )
