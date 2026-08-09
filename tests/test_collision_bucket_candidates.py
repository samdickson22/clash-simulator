import copy

import pytest

from clasher import battle
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.determinism_check import compute_rollout_digest


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_collision_bucket_candidates_preserve_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path,
):
    common = {
        "seed": 2301,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(battle, "_USE_COLLISION_BUCKET_CANDIDATES", False)
    scalar = compute_rollout_digest(**common)
    monkeypatch.setattr(battle, "_USE_COLLISION_BUCKET_CANDIDATES", True)
    bucketed = compute_rollout_digest(**common)

    assert bucketed.sha256 == scalar.sha256
    assert bucketed.mask_shadow_mismatches == scalar.mask_shadow_mismatches == 0


def test_bucket_candidates_include_data_driven_large_collision_radii(monkeypatch):
    source = BattleState(fast_path=True)
    stats = source.card_loader.get_card("Knight")
    assert stats is not None
    stats = copy.deepcopy(stats)
    stats.collision_radius = 3.0
    first = source._spawn_entity(Troop, Position(5.0, 16.0), 0, stats)
    source._spawn_entity(Troop, Position(10.0, 16.0), 1, stats)
    source._refresh_fast_path_caches()

    scalar = source.clone()
    bucketed = source.clone()
    monkeypatch.setattr(battle, "_USE_COLLISION_BUCKET_CANDIDATES", False)
    scalar_first = scalar.entities[first.id]
    assert isinstance(scalar_first, Troop)
    scalar._accumulate_troop_collision_for(scalar_first)

    monkeypatch.setattr(battle, "_USE_COLLISION_BUCKET_CANDIDATES", True)
    bucketed_first = bucketed.entities[first.id]
    assert isinstance(bucketed_first, Troop)
    bucketed._accumulate_troop_collision_for(bucketed_first)

    assert bucketed_first._movement_vector_count == scalar_first._movement_vector_count
    assert bucketed_first._movement_vector_x_units == scalar_first._movement_vector_x_units
    assert bucketed_first._movement_vector_y_units == scalar_first._movement_vector_y_units
