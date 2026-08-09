from __future__ import annotations

import copy

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.rl.determinism_check import compute_rollout_digest


def test_alive_building_cache_exact_match_skips_reference_refresh(monkeypatch):
    battle = BattleState(fast_path=True)
    battle._rebuild_alive_buildings_cache()

    def fail_reference(_battle):
        raise AssertionError("unchanged exact membership should not allocate")

    monkeypatch.setattr(
        BattleState,
        "_rebuild_alive_buildings_cache",
        fail_reference,
    )

    battle._refresh_alive_buildings_cache()


def test_alive_building_cache_membership_change_matches_reference():
    source = BattleState(fast_path=True)
    source._rebuild_alive_buildings_cache()
    stats = source.card_loader.get_card("Cannon")
    assert stats is not None
    source._spawn_entity(Building, Position(9.0, 15.0), 0, stats)

    reference = source.clone()
    optimized = source.clone()
    reference._rebuild_alive_buildings_cache()
    optimized._refresh_alive_buildings_cache()

    assert [entity.id for entity in optimized._alive_buildings] == [
        entity.id for entity in reference._alive_buildings
    ]
    assert optimized._building_cache_signature == reference._building_cache_signature


def test_alive_building_cache_same_id_replacement_preserves_reference_semantics():
    source = BattleState(fast_path=True)
    source._rebuild_alive_buildings_cache()
    original = source._alive_buildings[0]
    replacement = copy.deepcopy(original)
    source.entities[original.id] = replacement

    source._refresh_alive_buildings_cache()

    assert source._alive_buildings[0] is original
    assert source._building_cache_signature == tuple(
        sorted(entity.id for entity in source._alive_buildings)
    )


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_alive_building_cache_reuse_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8803,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }
    optimized_refresh = BattleState._refresh_alive_buildings_cache

    monkeypatch.setattr(
        BattleState,
        "_refresh_alive_buildings_cache",
        BattleState._rebuild_alive_buildings_cache,
    )
    reference = compute_rollout_digest(**common)
    monkeypatch.setattr(
        BattleState,
        "_refresh_alive_buildings_cache",
        optimized_refresh,
    )
    optimized = compute_rollout_digest(**common)

    assert optimized.sha256 == reference.sha256
    assert optimized.decisions == reference.decisions
    assert optimized.episodes_finished == reference.episodes_finished
    assert optimized.mask_shadow_checks == reference.mask_shadow_checks
    assert optimized.mask_shadow_mismatches == reference.mask_shadow_mismatches == 0
