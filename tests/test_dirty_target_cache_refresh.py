from __future__ import annotations

import pytest

from clasher import battle as battle_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Entity, Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_knight(
    battle: BattleState,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


def test_clean_target_cache_skips_ordinary_full_dynamic_scan(monkeypatch):
    battle = BattleState(fast_path=True)
    _spawn_knight(battle, 1, Position(9.0, 18.0))
    battle._refresh_fast_path_caches()
    calls = 0
    original = battle._refresh_fast_target_dynamic_values

    def counted(index: int, entity: Entity) -> None:
        nonlocal calls
        calls += 1
        original(index, entity)

    monkeypatch.setattr(battle, "_refresh_fast_target_dynamic_values", counted)
    monkeypatch.setattr(
        battle_module,
        "_USE_DIRTY_TARGET_CACHE_REFRESH",
        False,
    )
    battle._refresh_target_cache(trust_dirty=True)
    reference_calls = calls
    assert reference_calls == len(battle._target_entities)

    calls = 0
    monkeypatch.setattr(
        battle_module,
        "_USE_DIRTY_TARGET_CACHE_REFRESH",
        True,
    )
    battle._refresh_target_cache(trust_dirty=True)

    assert calls == len(battle._volatile_target_indices) == 0


def test_structural_invalidation_rebuilds_same_size_replacement():
    battle = BattleState(fast_path=True)
    removed = _spawn_knight(battle, 0, Position(8.0, 12.0))
    battle._refresh_fast_path_caches()
    old_positions = battle._target_pos_x

    del battle.entities[removed.id]
    replacement = _spawn_knight(battle, 1, Position(10.0, 20.0))
    assert len(battle.entities) == battle._target_cache_entity_count
    assert battle._target_cache_dirty

    battle._refresh_fast_path_caches()

    assert battle._target_pos_x is not old_positions
    assert removed.id not in battle._target_index_by_id
    assert replacement.id in battle._target_index_by_id
    assert not battle._target_cache_dirty


def test_clean_target_cache_refreshes_data_selected_stealth_entry():
    battle = BattleState(fast_path=True)
    target = _spawn_knight(battle, 1, Position(10.0, 20.0))
    target._stealth_until = 10_000
    battle._rebuild_target_cache()
    index = battle._target_index_by_id[target.id]
    assert index in battle._volatile_target_indices
    assert battle._target_stealth_until[index] == 10_000

    target._stealth_until = 0
    battle._refresh_target_cache(trust_dirty=True)

    assert battle._target_stealth_until[index] == 0


def test_dirty_target_cache_clone_owns_mutable_refresh_state():
    battle = BattleState(fast_path=True)
    target = _spawn_knight(battle, 0, Position(8.0, 12.0))
    target._stealth_until = 0
    battle._rebuild_target_cache()
    clone = battle.clone()

    assert clone._volatile_target_indices == battle._volatile_target_indices
    assert clone._volatile_target_indices
    assert clone._volatile_target_indices is not battle._volatile_target_indices
    clone.invalidate_target_cache()
    assert clone._target_cache_dirty
    assert not battle._target_cache_dirty


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_dirty_target_cache_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8911,
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
        "_USE_DIRTY_TARGET_CACHE_REFRESH",
        False,
    )
    reference = compute_rollout_digest(**common)
    monkeypatch.setattr(
        battle_module,
        "_USE_DIRTY_TARGET_CACHE_REFRESH",
        True,
    )
    candidate = compute_rollout_digest(**common)

    assert candidate.sha256 == reference.sha256
    assert candidate.mask_shadow_checks == reference.mask_shadow_checks
    assert candidate.mask_shadow_mismatches == reference.mask_shadow_mismatches == 0
