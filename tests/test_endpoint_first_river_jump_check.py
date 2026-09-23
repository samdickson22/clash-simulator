from __future__ import annotations

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, TargetType, Troop
from clasher.factory.dynamic_factory import building_from_values, troop_from_values


def _troop() -> Troop:
    stats = troop_from_values(
        name="TestMover",
        hitpoints=1000,
        damage=100,
        speed_logic_units_per_tick=60.0,
        range_tiles=1.0,
        sight_range_tiles=5.5,
        target_type="TID_TARGETS_GROUND",
        attacks_ground=True,
        attacks_air=False,
    )
    return Troop(
        id=1,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=stats,
        hitpoints=1000,
        max_hitpoints=1000,
        damage=100,
        range=1.0,
        sight_range=5.5,
        speed=60.0,
        target_type=TargetType.GROUND,
    )


def _target() -> Building:
    stats = building_from_values(
        name="TestTarget",
        hitpoints=1200,
        damage=0,
        range_tiles=0.0,
        sight_range_tiles=0.0,
        hit_speed_ms=1000,
        deploy_time_ms=0,
        collision_radius_tiles=1.0,
        lifetime_ms=None,
        target_type="TID_TARGETS_GROUND",
    )
    return Building(
        id=2,
        position=Position(9.0, 12.0),
        player_id=1,
        card_stats=stats,
        hitpoints=1200,
        max_hitpoints=1200,
        damage=0,
        range=0.0,
        sight_range=0.0,
    )


def _move_once(
    monkeypatch,
    *,
    endpoint_first: bool,
    endpoint_walkable: bool,
) -> tuple[tuple[float, float], list[tuple[float, float]], int]:
    battle = BattleState(fast_path=True)
    mover = _troop()
    target = _target()
    mover.battle_state = battle
    target.battle_state = battle
    battle.entities = {mover.id: mover, target.id: target}
    walkability_queries: list[tuple[float, float]] = []
    jump_calls = 0

    def walkable(position: Position, _mover: Troop) -> bool:
        walkability_queries.append((position.x, position.y))
        return (
            endpoint_walkable
            if position.y > mover.position.y + 1e-9
            else True
        )

    def try_jump(*_args, **_kwargs) -> bool:
        nonlocal jump_calls
        jump_calls += 1
        return True

    monkeypatch.setattr(
        entities_module,
        "_USE_ENDPOINT_FIRST_RIVER_JUMP_CHECK",
        endpoint_first,
    )
    monkeypatch.setattr(battle, "is_ground_position_walkable", walkable)
    monkeypatch.setattr(mover, "_try_start_river_jump", try_jump)
    mover._move_towards_target(target, battle.dt, battle)
    return (mover.position.x, mover.position.y), walkability_queries, jump_calls


def test_endpoint_first_skips_origin_query_for_walkable_move(monkeypatch) -> None:
    with monkeypatch.context() as reference_patch:
        reference_position, reference_queries, reference_jumps = _move_once(
            reference_patch,
            endpoint_first=False,
            endpoint_walkable=True,
        )
    with monkeypatch.context() as candidate_patch:
        candidate_position, candidate_queries, candidate_jumps = _move_once(
            candidate_patch,
            endpoint_first=True,
            endpoint_walkable=True,
        )

    assert candidate_position == reference_position
    assert reference_jumps == candidate_jumps == 0
    assert len(reference_queries) == 2
    assert len(candidate_queries) == 1


def test_endpoint_first_preserves_unwalkable_boundary_jump(monkeypatch) -> None:
    with monkeypatch.context() as reference_patch:
        reference_position, reference_queries, reference_jumps = _move_once(
            reference_patch,
            endpoint_first=False,
            endpoint_walkable=False,
        )
    with monkeypatch.context() as candidate_patch:
        candidate_position, candidate_queries, candidate_jumps = _move_once(
            candidate_patch,
            endpoint_first=True,
            endpoint_walkable=False,
        )

    assert candidate_position == reference_position
    assert reference_jumps == candidate_jumps == 1
    assert len(reference_queries) == len(candidate_queries) == 2
