from __future__ import annotations

import pytest

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_knight(
    battle: BattleState,
    player_id: int,
    position: Position,
):
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


@pytest.mark.parametrize("stealth_until", [0, -1])
def test_inactive_stealth_skips_battle_time_conversion(
    monkeypatch,
    stealth_until: int,
):
    battle = BattleState()
    target = _spawn_knight(battle, 1, Position(9.0, 16.0))
    target._stealth_until = stealth_until

    def fail_if_called(value: float) -> int:
        del value
        raise AssertionError("inactive stealth converted battle time")

    monkeypatch.setattr(
        entities_module,
        "logic_time_milliseconds",
        fail_if_called,
    )
    assert target.is_targetable_by(0)


def test_active_stealth_still_uses_current_battle_time(monkeypatch):
    battle = BattleState()
    target = _spawn_knight(battle, 1, Position(9.0, 16.0))
    target._stealth_until = 100
    calls = 0

    def current_time(value: float) -> int:
        nonlocal calls
        del value
        calls += 1
        return 50

    monkeypatch.setattr(
        entities_module,
        "logic_time_milliseconds",
        current_time,
    )
    assert not target.is_targetable_by(0)
    assert calls == 1


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_inactive_stealth_shortcut_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8837,
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
        "_DEFER_INACTIVE_STEALTH_TIME_LOOKUP",
        False,
    )
    baseline = compute_rollout_digest(**common)
    monkeypatch.setattr(
        entities_module,
        "_DEFER_INACTIVE_STEALTH_TIME_LOOKUP",
        True,
    )
    candidate = compute_rollout_digest(**common)

    assert candidate.sha256 == baseline.sha256
    assert candidate.decisions == baseline.decisions
    assert candidate.episodes_finished == baseline.episodes_finished
    assert candidate.mask_shadow_checks == baseline.mask_shadow_checks
    assert (
        candidate.mask_shadow_mismatches
        == baseline.mask_shadow_mismatches
        == 0
    )
