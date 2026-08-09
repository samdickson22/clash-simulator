from __future__ import annotations

import pytest

from clasher import battle as battle_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.rl.determinism_check import compute_rollout_digest


def test_alive_building_cache_contains_only_live_buildings():
    battle = BattleState(fast_path=True)
    battle._refresh_alive_buildings_cache()

    assert battle._alive_buildings
    assert all(
        isinstance(entity, Building) and entity.is_alive
        for entity in battle._alive_buildings
    )

    removed = battle._alive_buildings[0]
    removed.is_alive = False
    battle._refresh_alive_buildings_cache()

    assert removed not in battle._alive_buildings
    assert all(
        isinstance(entity, Building) and entity.is_alive
        for entity in battle._alive_buildings
    )


@pytest.mark.parametrize(
    ("position", "ignore_building_id"),
    [
        (Position(3.5, 6.5), None),
        (Position(9.0, 15.0), None),
        (Position(3.5, 6.5), 1),
    ],
)
def test_trusted_building_membership_matches_defensive_scan(
    monkeypatch,
    position: Position,
    ignore_building_id: int | None,
):
    battle = BattleState(fast_path=True)
    kwargs = {
        "mover_radius": 0.5,
        "ignore_building_id": ignore_building_id,
        "movement_collision": True,
    }

    monkeypatch.setattr(
        battle_module,
        "_USE_TRUSTED_ALIVE_BUILDING_MEMBERSHIP",
        False,
    )
    defensive = battle.is_position_occupied_by_building(position, **kwargs)
    monkeypatch.setattr(
        battle_module,
        "_USE_TRUSTED_ALIVE_BUILDING_MEMBERSHIP",
        True,
    )
    trusted = battle.is_position_occupied_by_building(position, **kwargs)

    assert trusted == defensive


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_trusted_building_membership_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8873,
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
        "_USE_TRUSTED_ALIVE_BUILDING_MEMBERSHIP",
        False,
    )
    defensive = compute_rollout_digest(**common)
    monkeypatch.setattr(
        battle_module,
        "_USE_TRUSTED_ALIVE_BUILDING_MEMBERSHIP",
        True,
    )
    trusted = compute_rollout_digest(**common)

    assert trusted.sha256 == defensive.sha256
    assert trusted.decisions == defensive.decisions
    assert trusted.episodes_finished == defensive.episodes_finished
    assert trusted.mask_shadow_checks == defensive.mask_shadow_checks
    assert trusted.mask_shadow_mismatches == defensive.mask_shadow_mismatches == 0
