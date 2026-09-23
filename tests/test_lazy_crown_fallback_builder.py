from __future__ import annotations

import pytest

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_attacker(battle: BattleState) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    return battle._spawn_entity(Troop, Position(9.0, 8.0), 0, stats)


def test_lazy_builder_preserves_complete_compatibility_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = BattleState(fast_path=True)
    attacker = _spawn_attacker(source)
    stats = source.card_loader.get_card("Cannon")
    assert stats is not None
    custom_crown = source._spawn_entity(
        Building,
        Position(9.0, 20.0),
        1,
        stats,
    )
    custom_crown._is_king_tower = True
    source.sync_fast_target_static_entity(custom_crown)

    monkeypatch.setattr(
        entities_module,
        "_USE_DIRECT_CACHED_CROWN_FALLBACK_SELECTION",
        False,
    )
    monkeypatch.setattr(
        entities_module,
        "_USE_LAZY_CROWN_FALLBACK_BUILDER",
        False,
    )
    eager = attacker.get_nearest_target(source.entities)
    monkeypatch.setattr(
        entities_module,
        "_USE_LAZY_CROWN_FALLBACK_BUILDER",
        True,
    )
    lazy = attacker.get_nearest_target(source.entities)

    assert lazy is eager


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_lazy_builder_preserves_fixed_seed_rollout(
    monkeypatch: pytest.MonkeyPatch,
    engine_fast_path: str,
) -> None:
    common = {
        "seed": 8969,
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
        "_USE_LAZY_CROWN_FALLBACK_BUILDER",
        False,
    )
    eager = compute_rollout_digest(**common)
    monkeypatch.setattr(
        entities_module,
        "_USE_LAZY_CROWN_FALLBACK_BUILDER",
        True,
    )
    lazy = compute_rollout_digest(**common)

    assert lazy.sha256 == eager.sha256
    assert lazy.mask_shadow_checks == eager.mask_shadow_checks
    assert lazy.mask_shadow_mismatches == eager.mask_shadow_mismatches == 0
