from __future__ import annotations

import pytest

from clasher import unit_traits
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Entity
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_entity(battle: BattleState, card_name: str) -> Entity:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(Position(9.0, 14.0), 0, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before
    )


@pytest.mark.parametrize("card_name", ["Knight", "RoyalGhost", "Minions"])
@pytest.mark.parametrize(
    ("dynamic_field", "dynamic_value"),
    [
        (None, None),
        ("_river_jump_active", True),
        ("_mk_leap_phase", "airborne"),
    ],
)
def test_direct_collision_plane_matches_defensive_entity_path(
    monkeypatch,
    card_name: str,
    dynamic_field: str | None,
    dynamic_value: object,
):
    entity = _spawn_entity(BattleState(), card_name)
    if dynamic_field is not None:
        setattr(entity, dynamic_field, dynamic_value)

    monkeypatch.setattr(unit_traits, "_USE_DIRECT_ENTITY_COLLISION_PLANE", False)
    defensive = unit_traits.uses_air_collision_plane(entity)
    monkeypatch.setattr(unit_traits, "_USE_DIRECT_ENTITY_COLLISION_PLANE", True)
    direct = unit_traits.uses_air_collision_plane(entity)

    assert direct == defensive


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_direct_collision_plane_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8797,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(unit_traits, "_USE_DIRECT_ENTITY_COLLISION_PLANE", False)
    defensive = compute_rollout_digest(**common)
    monkeypatch.setattr(unit_traits, "_USE_DIRECT_ENTITY_COLLISION_PLANE", True)
    direct = compute_rollout_digest(**common)

    assert direct.sha256 == defensive.sha256
    assert direct.decisions == defensive.decisions
    assert direct.episodes_finished == defensive.episodes_finished
    assert direct.mask_shadow_checks == defensive.mask_shadow_checks
    assert direct.mask_shadow_mismatches == defensive.mask_shadow_mismatches == 0
