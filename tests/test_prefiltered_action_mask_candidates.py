from __future__ import annotations

from collections import deque

import numpy as np
import pytest

from clasher.battle import BattleState
from clasher.rl import action_space as action_space_module
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.determinism_check import compute_rollout_digest
from clasher.spells import SPELL_REGISTRY


def _prepare_hand(battle: BattleState, player_id: int, card_name: str) -> None:
    player = battle.players[player_id]
    player.elixir = 20.0
    player.hand = [card_name] * 4
    player.deck = [card_name] * 8
    player.cycle_queue = deque(player.deck[4:])


@pytest.mark.parametrize("player_id", [0, 1])
def test_prefiltered_miner_candidates_skip_scalar_tower_rechecks(
    monkeypatch,
    player_id: int,
) -> None:
    battle = BattleState(fast_path=True)
    _prepare_hand(battle, player_id, "Miner")
    battle._refresh_fast_path_caches()
    action_space = DiscreteTileActionSpace()

    monkeypatch.setattr(
        battle.arena,
        "is_tower_tile",
        lambda *args, **kwargs: pytest.fail("candidate tower tile was rechecked"),
    )

    mask = action_space.legal_action_mask(battle, player_id, fast_path=True)
    assert mask[action_space.no_op_action]
    assert np.any(mask[: action_space.no_op_action])


@pytest.mark.parametrize("card_name", ["Log", "BarbarianBarrel", "RoyalDelivery"])
def test_prefiltered_territory_spell_skips_redundant_zone_rechecks(
    monkeypatch,
    card_name: str,
) -> None:
    battle = BattleState(fast_path=True)
    _prepare_hand(battle, 0, card_name)
    battle._refresh_fast_path_caches()
    action_space = DiscreteTileActionSpace()

    monkeypatch.setattr(
        battle.arena,
        "can_deploy_at",
        lambda *args, **kwargs: pytest.fail("candidate territory was rechecked"),
    )

    mask = action_space.legal_action_mask(battle, 0, fast_path=True)
    assert mask[action_space.no_op_action]
    assert np.any(mask[: action_space.no_op_action])


def test_walkability_predicate_remains_scalar_and_exact(monkeypatch) -> None:
    battle = BattleState(fast_path=True)
    _prepare_hand(battle, 0, "Fireball")
    battle._refresh_fast_path_caches()
    action_space = DiscreteTileActionSpace()
    spell = SPELL_REGISTRY["Fireball"]
    monkeypatch.setattr(spell, "requires_walkable_target", True)
    calls = 0
    original = battle.arena.can_deploy_at

    def counted(*args, **kwargs) -> bool:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(battle.arena, "can_deploy_at", counted)
    optimized = action_space.legal_action_mask(battle, 0, fast_path=True)
    assert calls > 0

    monkeypatch.setattr(
        action_space_module,
        "_USE_PREFILTERED_ACTION_MASK_CANDIDATES",
        False,
    )
    reference = action_space.legal_action_mask(battle, 0, fast_path=True)
    np.testing.assert_array_equal(reference, optimized)


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_prefiltered_candidates_preserve_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
) -> None:
    common = {
        "seed": 8933,
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
        "_USE_PREFILTERED_ACTION_MASK_CANDIDATES",
        False,
    )
    reference = compute_rollout_digest(**common)
    monkeypatch.setattr(
        action_space_module,
        "_USE_PREFILTERED_ACTION_MASK_CANDIDATES",
        True,
    )
    candidate = compute_rollout_digest(**common)

    assert candidate.sha256 == reference.sha256
    assert candidate.mask_shadow_checks == reference.mask_shadow_checks
    assert candidate.mask_shadow_mismatches == reference.mask_shadow_mismatches == 0
