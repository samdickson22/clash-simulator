from __future__ import annotations

import copy
import math

import pytest

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.balance import EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.determinism_check import compute_rollout_digest


def test_exact_bound_includes_discounted_large_crown_at_sight_edge() -> None:
    battle = BattleState(fast_path=True)
    attacker_stats = battle.card_loader.get_card("Knight")
    target_stats = battle.card_loader.get_card("Cannon")
    assert attacker_stats is not None
    assert target_stats is not None
    attacker = battle._spawn_entity(
        Troop,
        Position(9.0, 10.0),
        0,
        attacker_stats,
    )
    target_stats = copy.deepcopy(target_stats)
    target_stats.collision_radius = 2.0
    discount_sq_units = 1_200 * 1_200
    reach = (
        attacker.sight_range
        + target_stats.collision_radius
        + EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS / 1000.0
    )
    center_distance = math.sqrt(reach * reach + discount_sq_units / 1_000_000.0)
    target = battle._spawn_entity(
        Building,
        Position(9.0, attacker.position.y + center_distance - 1e-9),
        1,
        target_stats,
    )
    target._is_king_tower = True
    target._native_target_distance_discount_sq_units = discount_sq_units
    battle.sync_fast_target_static_entity(target)

    maximum_reach = (
        attacker.sight_range
        + battle._max_target_collision_radius
        + EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS / 1000.0
        + entities_module.GEOMETRY_BOUNDARY_EPSILON
    )
    query_radius = math.sqrt(
        maximum_reach * maximum_reach
        + battle._max_target_distance_discount_sq
    )
    candidates = battle.iter_entities_in_radius(
        attacker.position,
        query_radius,
        tight_bounds=True,
    )

    assert target in candidates
    assert attacker.is_within_sight(target)
    assert battle._max_target_distance_discount_sq == pytest.approx(1.44)


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_exact_target_bound_preserves_fixed_seed_rollout(
    monkeypatch: pytest.MonkeyPatch,
    engine_fast_path: str,
) -> None:
    common = {
        "seed": 8977,
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
        entities_module,
        "_USE_EXACT_TARGET_BUCKET_BOUND",
        False,
    )
    halo = compute_rollout_digest(**common)
    monkeypatch.setattr(
        entities_module,
        "_USE_EXACT_TARGET_BUCKET_BOUND",
        True,
    )
    exact = compute_rollout_digest(**common)

    assert exact.sha256 == halo.sha256
    assert exact.mask_shadow_checks == halo.mask_shadow_checks
    assert exact.mask_shadow_mismatches == halo.mask_shadow_mismatches == 0
