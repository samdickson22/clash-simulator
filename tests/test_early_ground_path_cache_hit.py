from __future__ import annotations

import copy

import pytest

from clasher import pathfinding
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_troop(
    battle: BattleState,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    troop = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    return troop


def test_early_ground_path_cache_hit_matches_reference(monkeypatch) -> None:
    reference = BattleState()
    reference.entities.clear()
    mover = _spawn_troop(reference, 0, Position(9.25, 8.75))
    target = _spawn_troop(reference, 1, Position(9.25, 14.25))
    pathfinding.ground_path_waypoint(
        reference,
        mover,
        target.position,
        target_entity=target,
    )
    optimized = copy.deepcopy(reference)
    optimized_mover = optimized.entities[mover.id]
    optimized_target = optimized.entities[target.id]

    monkeypatch.setattr(pathfinding, "_USE_EARLY_GROUND_PATH_CACHE_HIT", False)
    reference_waypoint = pathfinding.ground_path_waypoint(
        reference,
        mover,
        target.position,
        target_entity=target,
    )
    monkeypatch.setattr(pathfinding, "_USE_EARLY_GROUND_PATH_CACHE_HIT", True)
    optimized_waypoint = pathfinding.ground_path_waypoint(
        optimized,
        optimized_mover,
        optimized_target.position,
        target_entity=optimized_target,
    )

    assert optimized_waypoint == reference_waypoint
    assert optimized_mover._ground_path_cache_key == mover._ground_path_cache_key
    assert optimized_mover._native_ground_route_cells == mover._native_ground_route_cells
    assert optimized_mover._ground_path_backwards == mover._ground_path_backwards


def test_early_ground_path_cache_hit_skips_mover_start_quantization(
    monkeypatch,
) -> None:
    battle = BattleState()
    battle.entities.clear()
    mover = _spawn_troop(battle, 0, Position(9.25, 8.75))
    target = _spawn_troop(battle, 1, Position(9.25, 14.25))
    expected = pathfinding.ground_path_waypoint(
        battle,
        mover,
        target.position,
        target_entity=target,
    )
    original_cell_for_position = pathfinding._cell_for_position

    def fail_for_mover_start(position: Position) -> tuple[int, int]:
        if position is mover.position:
            raise AssertionError("retained route hit must not quantize mover start")
        return original_cell_for_position(position)

    monkeypatch.setattr(pathfinding, "_cell_for_position", fail_for_mover_start)
    monkeypatch.setattr(pathfinding, "_USE_EARLY_GROUND_PATH_CACHE_HIT", True)

    assert (
        pathfinding.ground_path_waypoint(
            battle,
            mover,
            target.position,
            target_entity=target,
        )
        == expected
    )


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_early_ground_path_cache_hit_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
) -> None:
    common = {
        "seed": 9075,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }
    monkeypatch.setattr(pathfinding, "_USE_EARLY_GROUND_PATH_CACHE_HIT", False)
    reference = compute_rollout_digest(**common)
    monkeypatch.setattr(pathfinding, "_USE_EARLY_GROUND_PATH_CACHE_HIT", True)
    optimized = compute_rollout_digest(**common)

    assert optimized.sha256 == reference.sha256
    assert optimized.mask_shadow_mismatches == reference.mask_shadow_mismatches == 0
