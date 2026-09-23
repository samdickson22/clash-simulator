from collections import deque

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import TimedExplosive
from clasher.rl import action_space as action_space_module
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.determinism_check import compute_rollout_digest


def _prepare_hand(battle: BattleState) -> None:
    cards = ["Knight", "Cannon", "Fireball", "Archers"]
    player = battle.players[0]
    player.elixir = player.max_elixir
    player.hand = cards.copy()
    player.deck = (cards * 2)[:8]
    player.cycle_queue = deque(player.deck[4:])


def test_deployment_blocker_guard_skips_empty_payload_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(fast_path=True)
    _prepare_hand(battle)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    calls = 0
    original = battle.is_deployment_payload_occupied

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(battle, "is_deployment_payload_occupied", counted)
    monkeypatch.setattr(
        action_space_module,
        "_USE_DEPLOYMENT_BLOCKER_GUARD",
        False,
    )
    reference = action_space.legal_action_mask(battle, 0, fast_path=True)
    reference_calls = calls
    monkeypatch.setattr(
        action_space_module,
        "_USE_DEPLOYMENT_BLOCKER_GUARD",
        True,
    )
    calls = 0
    guarded = action_space.legal_action_mask(battle, 0, fast_path=True)

    np.testing.assert_array_equal(guarded, reference)
    assert reference_calls > 0
    assert calls == 0


def test_deployment_blocker_guard_preserves_live_payload_occupancy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(fast_path=True)
    _prepare_hand(battle)
    balloon_stats = battle.card_loader.get_card("Balloon")
    assert balloon_stats is not None
    battle._spawn_troop(Position(9.5, 10.5), 1, balloon_stats)
    balloon = battle.entities[battle.next_entity_id - 1]
    balloon.deploy_delay_remaining = 0.0
    balloon.placement_pending = False
    balloon.take_damage(balloon.hitpoints)
    assert any(isinstance(entity, TimedExplosive) for entity in battle.entities.values())

    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    monkeypatch.setattr(
        action_space_module,
        "_USE_DEPLOYMENT_BLOCKER_GUARD",
        False,
    )
    reference = action_space.legal_action_mask(battle, 0, fast_path=True)
    monkeypatch.setattr(
        action_space_module,
        "_USE_DEPLOYMENT_BLOCKER_GUARD",
        True,
    )
    guarded = action_space.legal_action_mask(battle, 0, fast_path=True)

    np.testing.assert_array_equal(guarded, reference)
    assert not guarded[action_space.encode_action(0, 9, 10, 0)]
    assert not guarded[action_space.encode_action(1, 9, 10, 0)]


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_deployment_blocker_guard_preserves_fixed_rollout_digest(
    monkeypatch: pytest.MonkeyPatch,
    engine_fast_path: str,
) -> None:
    common = {
        "seed": 9989,
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
        action_space_module,
        "_USE_DEPLOYMENT_BLOCKER_GUARD",
        False,
    )
    reference = compute_rollout_digest(**common)
    monkeypatch.setattr(
        action_space_module,
        "_USE_DEPLOYMENT_BLOCKER_GUARD",
        True,
    )
    guarded = compute_rollout_digest(**common)

    assert guarded.sha256 == reference.sha256
    assert guarded.mask_shadow_checks == reference.mask_shadow_checks
    assert guarded.mask_shadow_mismatches == reference.mask_shadow_mismatches == 0
