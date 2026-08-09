import pytest

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_knight(battle: BattleState, player_id: int, position: Position) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_troop(position, player_id, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


@pytest.mark.parametrize("attacker_x", [3.0, 9.0, 15.0])
def test_preferred_crown_distance_matches_eager_distance(
    monkeypatch,
    attacker_x: float,
):
    battle = BattleState(fast_path=True)
    attacker = _spawn_knight(battle, 0, Position(attacker_x, 8.0))
    battle._refresh_fast_path_caches()

    monkeypatch.setattr(
        entities_module,
        "_PREFER_CROWN_FALLBACK_BEFORE_DISTANCE",
        False,
    )
    eager = attacker.get_nearest_target(battle.entities)
    monkeypatch.setattr(
        entities_module,
        "_PREFER_CROWN_FALLBACK_BEFORE_DISTANCE",
        True,
    )
    preferred_first = attacker.get_nearest_target(battle.entities)

    assert preferred_first is eager


def test_preferred_crown_filter_avoids_discarded_distance_work(monkeypatch):
    battle = BattleState(fast_path=True)
    attacker = _spawn_knight(battle, 0, Position(3.0, 8.0))
    battle._refresh_fast_path_caches()
    calls = 0
    original = attacker.native_target_distance_to

    def counted(target):
        nonlocal calls
        calls += 1
        return original(target)

    monkeypatch.setattr(attacker, "native_target_distance_to", counted)
    attacker.get_nearest_target(battle.entities)

    assert calls == 1


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_preferred_crown_distance_preserves_fixed_seed_rollout(
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
        entities_module,
        "_PREFER_CROWN_FALLBACK_BEFORE_DISTANCE",
        False,
    )
    eager = compute_rollout_digest(**common)
    monkeypatch.setattr(
        entities_module,
        "_PREFER_CROWN_FALLBACK_BEFORE_DISTANCE",
        True,
    )
    preferred_first = compute_rollout_digest(**common)

    assert preferred_first.sha256 == eager.sha256
    assert preferred_first.mask_shadow_mismatches == eager.mask_shadow_mismatches == 0
