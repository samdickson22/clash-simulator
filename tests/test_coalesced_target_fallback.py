import pytest

from clasher import entities
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_knight(
    battle: BattleState,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    battle._spawn_troop(position, player_id, stats)
    troop = battle.entities[battle.next_entity_id - 1]
    assert isinstance(troop, Troop)
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    return troop


@pytest.mark.parametrize("enemy_in_sight", [False, True])
def test_scalar_and_vector_selectors_report_same_fallback_status(
    monkeypatch,
    enemy_in_sight,
):
    battle = BattleState(fast_path=True)
    attacker = _spawn_knight(battle, 0, Position(9.0, 8.0))
    if enemy_in_sight:
        _spawn_knight(battle, 1, Position(9.0, 9.0))
    battle._refresh_fast_path_caches()

    monkeypatch.setattr(entities, "_FAST_TARGET_VECTOR_MIN_SIZE", 10_000)
    scalar_target, scalar_fallback = attacker.get_nearest_target(
        battle.entities,
        _return_fallback_used=True,
    )
    monkeypatch.setattr(entities, "_FAST_TARGET_VECTOR_MIN_SIZE", 0)
    vector_target, vector_fallback = attacker.get_nearest_target(
        battle.entities,
        _return_fallback_used=True,
    )

    assert vector_target is scalar_target
    assert vector_fallback is scalar_fallback is (not enemy_in_sight)


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_coalesced_fallback_scan_preserves_fixed_seed_rollout(
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

    monkeypatch.setattr(entities, "_COALESCE_CROWN_FALLBACK_TARGET_SCAN", False)
    duplicate = compute_rollout_digest(**common)
    monkeypatch.setattr(entities, "_COALESCE_CROWN_FALLBACK_TARGET_SCAN", True)
    coalesced = compute_rollout_digest(**common)

    assert coalesced.sha256 == duplicate.sha256
    assert coalesced.mask_shadow_mismatches == duplicate.mask_shadow_mismatches == 0
