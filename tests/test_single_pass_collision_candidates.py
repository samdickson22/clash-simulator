from __future__ import annotations

import pytest

from clasher import battle as battle_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn(
    battle: BattleState,
    entity_type: type[Troop | Building],
    card_name: str,
    position: Position,
    player_id: int,
) -> Troop | Building:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    return battle._spawn_entity(entity_type, position, player_id, stats)


def test_single_pass_collision_matches_two_candidate_scans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = BattleState(fast_path=True)
    mover = _spawn(source, Troop, "Knight", Position(9.0, 14.0), 0)
    _spawn(source, Building, "Cannon", Position(9.0, 14.6), 1)
    _spawn(source, Troop, "Knight", Position(9.3, 14.0), 1)
    source._refresh_fast_path_caches()

    reference = source.clone()
    candidate = source.clone()
    reference_mover = reference.entities[mover.id]
    candidate_mover = candidate.entities[mover.id]
    assert isinstance(reference_mover, Troop)
    assert isinstance(candidate_mover, Troop)

    monkeypatch.setattr(
        battle_module,
        "_USE_SINGLE_PASS_COLLISION_CANDIDATES",
        False,
    )
    reference._accumulate_troop_collision_for(reference_mover)
    monkeypatch.setattr(
        battle_module,
        "_USE_SINGLE_PASS_COLLISION_CANDIDATES",
        True,
    )
    candidate._accumulate_troop_collision_for(candidate_mover)

    assert candidate_mover._movement_vector_count == (
        reference_mover._movement_vector_count
    )
    assert candidate_mover._movement_vector_x_units == (
        reference_mover._movement_vector_x_units
    )
    assert candidate_mover._movement_vector_y_units == (
        reference_mover._movement_vector_y_units
    )


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_single_pass_collision_preserves_fixed_seed_rollout(
    monkeypatch: pytest.MonkeyPatch,
    engine_fast_path: str,
) -> None:
    common = {
        "seed": 8963,
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
        "_USE_SINGLE_PASS_COLLISION_CANDIDATES",
        False,
    )
    reference = compute_rollout_digest(**common)
    monkeypatch.setattr(
        battle_module,
        "_USE_SINGLE_PASS_COLLISION_CANDIDATES",
        True,
    )
    candidate = compute_rollout_digest(**common)

    assert candidate.sha256 == reference.sha256
    assert candidate.mask_shadow_checks == reference.mask_shadow_checks
    assert candidate.mask_shadow_mismatches == reference.mask_shadow_mismatches == 0
