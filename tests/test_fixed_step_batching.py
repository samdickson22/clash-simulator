import math

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.engine import BattleEngine
from clasher.entities import Building, Troop


def _active_xbow_duel() -> BattleState:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1

    xbow = battle._spawn_entity(
        Building,
        Position(9.0, 12.0),
        0,
        battle.card_loader.get_card("Xbow"),
    )
    battle._spawn_unit_at_position(
        Position(9.0, 13.0),
        1,
        battle.card_loader.get_card("Knight"),
    )
    knight = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
    )
    for entity in (xbow, knight):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity.on_spawn()
    knight.apply_stun(99.0)
    xbow.attack_cooldown = 0.0
    return battle


def _interaction_snapshot(battle: BattleState) -> tuple:
    return (
        battle.tick,
        battle.time,
        tuple(
            (
                entity.id,
                type(entity).__name__,
                getattr(getattr(entity, "card_stats", None), "name", None),
                entity.position.x,
                entity.position.y,
                entity.hitpoints,
                entity.is_alive,
                getattr(entity, "target_id", None),
                getattr(entity, "attack_cooldown", None),
                getattr(entity, "deploy_delay_remaining", None),
            )
            for entity in battle.entities.values()
        ),
    )


def test_speed_factor_batches_native_logic_ticks_without_changing_interactions():
    batched = _active_xbow_duel()
    singles = _active_xbow_duel()

    batched.step(speed_factor=10.0)
    for _ in range(10):
        singles.step()

    assert _interaction_snapshot(batched) == _interaction_snapshot(singles)


def test_fractional_speed_factor_accumulates_complete_native_ticks_only():
    battle = BattleState()

    battle.step(speed_factor=0.5)
    assert battle.tick == 0
    assert battle.time == 0.0

    battle.step(speed_factor=0.5)
    assert battle.tick == 1
    assert battle.time == pytest.approx(battle.dt)


def test_battle_engine_speed_batching_respects_native_tick_budget():
    engine = BattleEngine()
    engine.create_battle()
    callback_ticks = []

    engine.run_battle(
        max_ticks=23,
        speed_factor=10.0,
        on_tick=lambda battle: callback_ticks.append(battle.tick),
    )

    assert engine.battle is not None
    assert engine.battle.tick == 23
    assert engine.battle.time == pytest.approx(23 * engine.battle.dt)
    assert callback_ticks == [10, 20, 23]


@pytest.mark.parametrize("speed_factor", [-1.0, math.inf, math.nan])
def test_battle_rejects_invalid_speed_factors(speed_factor):
    with pytest.raises(ValueError):
        BattleState().step(speed_factor=speed_factor)


@pytest.mark.parametrize("speed_factor", [0.0, -1.0, math.inf, math.nan])
def test_engine_rejects_non_progressing_speed_factors(speed_factor):
    with pytest.raises(ValueError):
        BattleEngine().run_battle(max_ticks=1, speed_factor=speed_factor)
