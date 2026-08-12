from dataclasses import dataclass

import pytest

from clasher import battle as battle_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.mechanics.mechanic_base import BaseMechanic
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


@dataclass
class _TargetingBlocker(BaseMechanic):
    blocked: bool = False

    def blocks_targeting(self, entity: Troop) -> bool:
        del entity
        return self.blocked


def test_static_targetability_skips_ordinary_predicate_refresh(monkeypatch):
    battle = BattleState(fast_path=True)
    troop = _spawn_troop(battle, "Knight", 1, Position(9.0, 18.0))
    battle._refresh_fast_path_caches()
    index = battle._target_index_by_id[troop.id]
    assert not battle._target_requires_targetability_check[index]

    def fail_if_called(player_id: int, **kwargs: object) -> bool:
        del player_id, kwargs
        raise AssertionError("ordinary targetability predicate was refreshed")

    monkeypatch.setattr(troop, "is_targetable_by", fail_if_called)
    battle._refresh_target_cache()
    battle.sync_fast_target_entity(troop)
    assert battle._target_is_targetable[index]


def test_dynamic_targetability_mechanic_retains_full_refresh():
    battle = BattleState(fast_path=True)
    troop = _spawn_troop(battle, "Knight", 1, Position(9.0, 18.0))
    blocker = _TargetingBlocker()
    troop.mechanics.append(blocker)
    battle._rebuild_target_cache()
    index = battle._target_index_by_id[troop.id]
    assert battle._target_requires_targetability_check[index]
    assert battle._target_is_targetable[index]

    blocker.blocked = True
    battle._refresh_target_cache()
    assert not battle._target_is_targetable[index]

    blocker.blocked = False
    battle.sync_fast_target_entity(troop)
    assert battle._target_is_targetable[index]


def test_entity_sync_reuses_cached_targetability_requirement(monkeypatch):
    battle = BattleState(fast_path=True)
    troop = _spawn_troop(battle, "Knight", 1, Position(9.0, 18.0))
    blocker = _TargetingBlocker(blocked=True)
    troop.mechanics.append(blocker)
    battle._rebuild_target_cache()
    index = battle._target_index_by_id[troop.id]
    calls = 0
    original = battle._requires_targetability_check

    def counted(entity):
        nonlocal calls
        calls += 1
        return original(entity)

    monkeypatch.setattr(battle, "_requires_targetability_check", counted)
    monkeypatch.setattr(
        battle_module,
        "_USE_CACHED_TARGETABILITY_REQUIREMENT",
        False,
    )
    battle.sync_fast_target_entity(troop)
    assert calls == 1
    assert not battle._target_is_targetable[index]

    calls = 0
    blocker.blocked = False
    monkeypatch.setattr(
        battle_module,
        "_USE_CACHED_TARGETABILITY_REQUIREMENT",
        True,
    )
    battle.sync_fast_target_entity(troop)
    assert calls == 0
    assert battle._target_is_targetable[index]


def test_targetability_classification_cache_is_clone_isolated():
    battle = BattleState(fast_path=True)
    troop = _spawn_troop(battle, "Knight", 1, Position(9.0, 18.0))
    battle._refresh_fast_path_caches()
    clone = battle.clone()
    index = battle._target_index_by_id[troop.id]

    assert (
        clone._target_requires_targetability_check
        is not battle._target_requires_targetability_check
    )
    clone._target_requires_targetability_check[index] = True
    assert not battle._target_requires_targetability_check[index]


def test_stealth_timestamp_remains_independent_of_static_targetability():
    battle = BattleState(fast_path=True)
    attacker = _spawn_troop(battle, "Knight", 0, Position(9.0, 14.0))
    target = _spawn_troop(battle, "Knight", 1, Position(9.0, 16.0))
    target._stealth_until = 10_000
    battle._rebuild_target_cache()
    index = battle._target_index_by_id[target.id]

    assert not battle._target_requires_targetability_check[index]
    assert battle._target_is_targetable[index]
    assert attacker.get_nearest_target(battle.entities) is not target

    target._stealth_until = 0
    battle.sync_fast_target_entity(target)
    assert attacker.get_nearest_target(battle.entities) is target


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_static_targetability_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8819,
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
        "_USE_STATIC_TARGETABILITY_CLASSIFICATION",
        False,
    )
    baseline = compute_rollout_digest(**common)
    monkeypatch.setattr(
        battle_module,
        "_USE_STATIC_TARGETABILITY_CLASSIFICATION",
        True,
    )
    classified = compute_rollout_digest(**common)

    assert classified.sha256 == baseline.sha256
    assert classified.mask_shadow_mismatches == baseline.mask_shadow_mismatches == 0


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_cached_sync_targetability_requirement_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8827,
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
        "_USE_CACHED_TARGETABILITY_REQUIREMENT",
        False,
    )
    recomputed = compute_rollout_digest(**common)
    monkeypatch.setattr(
        battle_module,
        "_USE_CACHED_TARGETABILITY_REQUIREMENT",
        True,
    )
    cached = compute_rollout_digest(**common)

    assert cached.sha256 == recomputed.sha256
    assert cached.mask_shadow_checks == recomputed.mask_shadow_checks
    assert cached.mask_shadow_mismatches == recomputed.mask_shadow_mismatches == 0
