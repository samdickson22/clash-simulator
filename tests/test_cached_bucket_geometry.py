from __future__ import annotations

import pytest

from clasher import battle as battle_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_troop(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


@pytest.mark.parametrize("cell_size", [0.5, 2.0, 3.25])
def test_cached_bucket_geometry_matches_recomputed_bounds(
    monkeypatch,
    cell_size: float,
):
    battle = BattleState(fast_path=True)
    battle._bucket_cell_size = cell_size
    for index, position in enumerate(
        (
            Position(0.5, 0.5),
            Position(9.0, 15.0),
            Position(17.5, 31.5),
        )
    ):
        _spawn_troop(battle, "Knight", index % 2, position)
    battle._refresh_fast_path_caches()

    monkeypatch.setattr(battle_module, "_USE_CACHED_BUCKET_GEOMETRY", False)
    recomputed = battle.iter_entities_in_radius(Position(9.0, 15.0), 20.0)
    monkeypatch.setattr(battle_module, "_USE_CACHED_BUCKET_GEOMETRY", True)
    cached = battle.iter_entities_in_radius(Position(9.0, 15.0), 20.0)

    assert [entity.id for entity in cached] == [entity.id for entity in recomputed]


def test_bucket_geometry_cache_is_clone_isolated():
    battle = BattleState(fast_path=True)
    clone = battle.clone()
    clone._entity_bucket_inverse_cell_size = 99.0
    clone._entity_bucket_grid_height = 99

    assert battle._entity_bucket_inverse_cell_size != 99.0
    assert battle._entity_bucket_grid_height != 99


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_cached_bucket_geometry_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8867,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(battle_module, "_USE_CACHED_BUCKET_GEOMETRY", False)
    recomputed = compute_rollout_digest(**common)
    monkeypatch.setattr(battle_module, "_USE_CACHED_BUCKET_GEOMETRY", True)
    cached = compute_rollout_digest(**common)

    assert cached.sha256 == recomputed.sha256
    assert cached.decisions == recomputed.decisions
    assert cached.episodes_finished == recomputed.episodes_finished
    assert cached.mask_shadow_checks == recomputed.mask_shadow_checks
    assert cached.mask_shadow_mismatches == recomputed.mask_shadow_mismatches == 0
