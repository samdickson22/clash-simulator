from __future__ import annotations

import pytest

from clasher import battle as battle_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_knight(
    battle: BattleState,
    position: Position,
    player_id: int,
) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    return battle._spawn_entity(Troop, position, player_id, stats)


def test_tight_bounds_keep_every_center_inside_interaction_radius() -> None:
    battle = BattleState(fast_path=True)
    center = Position(5.0, 16.0)
    near = _spawn_knight(battle, Position(5.99, 16.0), 1)
    far = _spawn_knight(battle, Position(8.1, 16.0), 1)
    battle._refresh_fast_path_caches()

    halo = battle.iter_entities_in_radius(center, 1.0, tight_bounds=False)
    tight = battle.iter_entities_in_radius(center, 1.0, tight_bounds=True)

    assert near in tight
    assert far in halo
    assert far not in tight


def test_tight_bounds_cover_every_bucket_intersecting_query_square() -> None:
    battle = BattleState(fast_path=True)
    center = Position(8.37, 15.61)
    radius = 1.73
    for cell_y in range(battle.arena.height):
        for cell_x in range(battle.arena.width):
            if (
                cell_x <= center.x + radius
                and cell_x + 1.0 >= center.x - radius
                and cell_y <= center.y + radius
                and cell_y + 1.0 >= center.y - radius
            ):
                _spawn_knight(
                    battle,
                    Position(cell_x + 0.5, cell_y + 0.5),
                    (cell_x + cell_y) % 2,
                )
    battle._refresh_fast_path_caches()

    expected = {
        entity.id
        for entity in battle.entities.values()
        if abs(entity.position.x - center.x) <= radius
        and abs(entity.position.y - center.y) <= radius
    }
    actual = {
        entity.id
        for entity in battle.iter_entities_in_radius(
            center,
            radius,
            tight_bounds=True,
        )
    }

    assert expected <= actual


def test_tight_bounds_preserve_collision_accumulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = BattleState(fast_path=True)
    mover = _spawn_knight(source, Position(9.0, 14.0), 0)
    _spawn_knight(source, Position(9.3, 14.0), 1)
    _spawn_knight(source, Position(12.0, 14.0), 1)
    source._refresh_fast_path_caches()
    reference = source.clone()
    candidate = source.clone()
    reference_mover = reference.entities[mover.id]
    candidate_mover = candidate.entities[mover.id]
    assert isinstance(reference_mover, Troop)
    assert isinstance(candidate_mover, Troop)

    monkeypatch.setattr(
        battle_module,
        "_USE_TIGHT_INTERACTION_BUCKET_BOUNDS",
        False,
    )
    reference._accumulate_troop_collision_for(reference_mover)
    monkeypatch.setattr(
        battle_module,
        "_USE_TIGHT_INTERACTION_BUCKET_BOUNDS",
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
def test_tight_bounds_preserve_fixed_seed_rollout(
    monkeypatch: pytest.MonkeyPatch,
    engine_fast_path: str,
) -> None:
    common = {
        "seed": 8973,
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
        "_USE_TIGHT_INTERACTION_BUCKET_BOUNDS",
        False,
    )
    halo = compute_rollout_digest(**common)
    monkeypatch.setattr(
        battle_module,
        "_USE_TIGHT_INTERACTION_BUCKET_BOUNDS",
        True,
    )
    tight = compute_rollout_digest(**common)

    assert tight.sha256 == halo.sha256
    assert tight.mask_shadow_checks == halo.mask_shadow_checks
    assert tight.mask_shadow_mismatches == halo.mask_shadow_mismatches == 0
