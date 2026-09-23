import pytest

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_knight(battle: BattleState, x: float) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_troop(Position(x, 8.0), 0, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


def _selected_with_mode(
    monkeypatch,
    attacker: Troop,
    battle: BattleState,
    *,
    single_pass: bool,
):
    monkeypatch.setattr(
        entities_module,
        "_USE_SINGLE_PASS_CACHED_CROWN_FALLBACK",
        single_pass,
    )
    return attacker.get_nearest_target(battle.entities)


@pytest.mark.parametrize("attacker_x", [3.0, 9.0, 15.0])
@pytest.mark.parametrize("dead_slot", [None, "king", "left", "right"])
def test_single_pass_crown_fallback_matches_partitioned_reference(
    monkeypatch,
    attacker_x: float,
    dead_slot: str | None,
):
    battle = BattleState(fast_path=True)
    attacker = _spawn_knight(battle, attacker_x)
    if dead_slot is not None:
        tower = next(
            entity
            for entity in battle.entities.values()
            if entity.player_id == 1
            and getattr(entity, "_crown_tower_slot", None) == dead_slot
        )
        tower.is_alive = False
    battle._refresh_fast_path_caches()

    reference = _selected_with_mode(
        monkeypatch,
        attacker,
        battle,
        single_pass=False,
    )
    candidate = _selected_with_mode(
        monkeypatch,
        attacker,
        battle,
        single_pass=True,
    )

    assert candidate is reference


def test_unclassified_custom_crown_uses_reference_classifier(monkeypatch):
    battle = BattleState(fast_path=True)
    attacker = _spawn_knight(battle, 9.0)
    stats = battle.card_loader.get_card("Cannon")
    assert stats is not None
    custom_crown = battle._spawn_entity(
        Building,
        Position(9.0, 20.0),
        1,
        stats,
    )
    custom_crown._is_king_tower = True
    battle.sync_fast_target_static_entity(custom_crown)

    reference = _selected_with_mode(
        monkeypatch,
        attacker,
        battle,
        single_pass=False,
    )
    candidate = _selected_with_mode(
        monkeypatch,
        attacker,
        battle,
        single_pass=True,
    )

    assert getattr(custom_crown, "_crown_tower_slot", None) is None
    assert candidate is reference


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_single_pass_crown_fallback_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8849,
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
        "_USE_SINGLE_PASS_CACHED_CROWN_FALLBACK",
        False,
    )
    reference = compute_rollout_digest(**common)
    monkeypatch.setattr(
        entities_module,
        "_USE_SINGLE_PASS_CACHED_CROWN_FALLBACK",
        True,
    )
    single_pass = compute_rollout_digest(**common)

    assert single_pass.sha256 == reference.sha256
    assert single_pass.mask_shadow_checks == reference.mask_shadow_checks
    assert single_pass.mask_shadow_mismatches == reference.mask_shadow_mismatches == 0
