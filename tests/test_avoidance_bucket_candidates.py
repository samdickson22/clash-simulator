from __future__ import annotations

import copy

import pytest

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.determinism_check import compute_rollout_digest


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_avoidance_bucket_candidates_preserve_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8789,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(entities_module, "_USE_AVOIDANCE_BUCKET_CANDIDATES", False)
    full_scan = compute_rollout_digest(**common)
    monkeypatch.setattr(entities_module, "_USE_AVOIDANCE_BUCKET_CANDIDATES", True)
    bucketed = compute_rollout_digest(**common)

    assert bucketed.sha256 == full_scan.sha256
    assert bucketed.decisions == full_scan.decisions
    assert bucketed.episodes_finished == full_scan.episodes_finished
    assert bucketed.mask_shadow_checks == full_scan.mask_shadow_checks
    assert bucketed.mask_shadow_mismatches == full_scan.mask_shadow_mismatches == 0


def test_avoidance_buckets_include_data_driven_large_collision_radii(monkeypatch):
    source = BattleState(fast_path=True)
    stats = source.card_loader.get_card("Knight")
    assert stats is not None
    large_stats = copy.deepcopy(stats)
    large_stats.collision_radius = 3.0
    mover = source._spawn_entity(Troop, Position(5.0, 16.0), 0, stats)
    other = source._spawn_entity(Troop, Position(8.5, 16.0), 1, large_stats)
    mover._movement_target_id = other.id
    mover._facing_x_units = 1000
    mover._facing_y_units = 0
    source._refresh_fast_path_caches()

    full_scan = source.clone()
    bucketed = source.clone()
    monkeypatch.setattr(entities_module, "_USE_AVOIDANCE_BUCKET_CANDIDATES", False)
    full_scan_mover = full_scan.entities[mover.id]
    assert isinstance(full_scan_mover, Troop)
    full_scan_mover._update_native_avoidance(full_scan)

    monkeypatch.setattr(entities_module, "_USE_AVOIDANCE_BUCKET_CANDIDATES", True)
    bucketed_mover = bucketed.entities[mover.id]
    assert isinstance(bucketed_mover, Troop)
    bucketed_mover._update_native_avoidance(bucketed)

    assert bucketed_mover._native_avoidance == full_scan_mover._native_avoidance
