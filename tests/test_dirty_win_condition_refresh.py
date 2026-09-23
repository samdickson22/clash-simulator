from __future__ import annotations

import copy

import pytest

from clasher import battle as battle_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.determinism_check import compute_rollout_digest
from clasher.spells import HealSpell


def _state(battle: BattleState) -> tuple[object, ...]:
    return (
        battle.tick,
        battle.time,
        battle.sudden_death,
        battle.game_over,
        battle.winner,
        tuple(
            value
            for player in battle.players
            for value in (
                player.left_tower_hp,
                player.right_tower_hp,
                player.king_tower_hp,
            )
        ),
    )


def test_dirty_win_refresh_publishes_tower_damage_exactly(monkeypatch) -> None:
    reference = BattleState()
    target = next(
        entity
        for entity in reference.entities.values()
        if getattr(entity, "_crown_tower_slot", None) == "left"
        and entity.player_id == 1
    )
    optimized = copy.deepcopy(reference)
    optimized_target = optimized.entities[target.id]
    target.take_damage(137)
    optimized_target.take_damage(137)

    monkeypatch.setattr(
        battle_module,
        "_USE_DIRTY_WIN_CONDITION_REFRESH",
        False,
    )
    reference.step()
    monkeypatch.setattr(
        battle_module,
        "_USE_DIRTY_WIN_CONDITION_REFRESH",
        True,
    )
    optimized.step()

    assert _state(optimized) == _state(reference)
    assert not optimized._win_conditions_dirty


def test_clean_win_refresh_still_crosses_overtime_boundary(monkeypatch) -> None:
    reference = BattleState()
    reference.time = reference.overtime_start_time - reference.dt
    reference._check_win_conditions()
    optimized = copy.deepcopy(reference)

    monkeypatch.setattr(
        battle_module,
        "_USE_DIRTY_WIN_CONDITION_REFRESH",
        False,
    )
    reference.step()
    monkeypatch.setattr(
        battle_module,
        "_USE_DIRTY_WIN_CONDITION_REFRESH",
        True,
    )
    optimized.step()

    assert _state(optimized) == _state(reference)
    assert optimized.sudden_death


def test_healed_crown_tower_marks_win_refresh_dirty() -> None:
    battle = BattleState()
    target = next(
        entity
        for entity in battle.entities.values()
        if getattr(entity, "_crown_tower_slot", None) == "left"
        and entity.player_id == 0
    )
    target.take_damage(200)
    battle._check_win_conditions()
    assert not battle._win_conditions_dirty

    spell = HealSpell(
        name="Test Heal",
        mana_cost=0,
        radius=1.0,
        heal_amount=100.0,
    )
    assert spell.cast(
        battle,
        target.player_id,
        Position(target.position.x, target.position.y),
    )

    assert battle._win_conditions_dirty


def test_dead_crown_cleanup_marks_win_refresh_dirty() -> None:
    battle = BattleState()
    target = next(
        entity
        for entity in battle.entities.values()
        if getattr(entity, "_crown_tower_slot", None) == "right"
        and entity.player_id == 1
    )
    battle._check_win_conditions()
    target.is_alive = False

    battle._cleanup_dead_entities()

    assert battle._win_conditions_dirty


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_dirty_win_refresh_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
) -> None:
    common = {
        "seed": 9091,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }
    monkeypatch.setattr(
        battle_module,
        "_USE_DIRTY_WIN_CONDITION_REFRESH",
        False,
    )
    reference = compute_rollout_digest(**common)
    monkeypatch.setattr(
        battle_module,
        "_USE_DIRTY_WIN_CONDITION_REFRESH",
        True,
    )
    optimized = compute_rollout_digest(**common)

    assert optimized.sha256 == reference.sha256
    assert optimized.mask_shadow_mismatches == reference.mask_shadow_mismatches == 0
