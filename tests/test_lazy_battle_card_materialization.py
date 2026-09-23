import pytest

from clasher import battle as battle_module
from clasher.battle import BattleState
from clasher.rl.determinism_check import compute_rollout_digest


def test_battle_materializes_card_wrappers_only_on_lookup(monkeypatch):
    monkeypatch.setattr(
        battle_module,
        "_EAGERLY_MATERIALIZE_BATTLE_CARDS",
        False,
    )
    battle = BattleState(fast_path=True)

    assert battle.card_loader._cards == {}
    knight = battle.card_loader.get_card("Knight")

    assert knight is not None
    assert battle.card_loader._cards == {"Knight": knight}
    assert battle.card_loader.get_card("Knight") is knight


def test_lazy_and_eager_card_wrappers_are_equal_and_battle_local(monkeypatch):
    monkeypatch.setattr(
        battle_module,
        "_EAGERLY_MATERIALIZE_BATTLE_CARDS",
        True,
    )
    eager_battle = BattleState(fast_path=True)
    eager = eager_battle.card_loader.get_card("Knight")
    assert eager is not None

    monkeypatch.setattr(
        battle_module,
        "_EAGERLY_MATERIALIZE_BATTLE_CARDS",
        False,
    )
    lazy_battle = BattleState(fast_path=True)
    lazy = lazy_battle.card_loader.get_card("Knight")
    assert lazy is not None

    assert vars(lazy) == vars(eager)
    assert lazy is not eager
    lazy.hitpoints = 1
    assert eager.hitpoints != lazy.hitpoints


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_lazy_card_materialization_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8861,
        "decisions": 64,
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
        "_EAGERLY_MATERIALIZE_BATTLE_CARDS",
        True,
    )
    eager = compute_rollout_digest(**common)
    monkeypatch.setattr(
        battle_module,
        "_EAGERLY_MATERIALIZE_BATTLE_CARDS",
        False,
    )
    lazy = compute_rollout_digest(**common)

    assert lazy.sha256 == eager.sha256
    assert lazy.mask_shadow_checks == eager.mask_shadow_checks
    assert lazy.mask_shadow_mismatches == eager.mask_shadow_mismatches == 0
