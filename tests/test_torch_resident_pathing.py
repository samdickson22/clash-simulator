from __future__ import annotations

import math
import random
from typing import TypedDict

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.native_tilemap import native_spawn_tile_blocked
from clasher.pathfinding import (
    _cached_standard_grid_route,
    _cell_for_position,
    _compute_native_route_goal_cell_units,
    ground_path_waypoint,
)
from clasher.torch_sim.resident_pathing import (
    HALF_TILE_LOGIC_UNITS,
    TensorResidentPathCache,
    plan_standard_routes,
    tensor_route_goal_cells,
    validate_resident_path_device,
)

DEVICES = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])


class _PlanArguments(TypedDict):
    entity_id: torch.Tensor
    active: torch.Tensor
    mover_position_units: torch.Tensor
    target_position_units: torch.Tensor
    required_range_units: torch.Tensor
    lane_id: torch.Tensor
    jump_height: torch.Tensor
    direct_single_node: torch.Tensor


def _expected_goal(
    mover: tuple[int, int],
    target: tuple[int, int],
    required_range: int,
) -> tuple[int, int] | None:
    return _compute_native_route_goal_cell_units(
        mover[0], mover[1], target[0], target[1], required_range
    )


def _route_moves_backwards(
    mover: tuple[int, int],
    target: tuple[int, int],
    retained: tuple[tuple[int, int], ...],
) -> bool:
    origin = math.isqrt((mover[0] - target[0]) ** 2 + (mover[1] - target[1]) ** 2)
    return any(
        math.isqrt(
            (cell[0] * HALF_TILE_LOGIC_UNITS + 250 - target[0]) ** 2
            + (cell[1] * HALF_TILE_LOGIC_UNITS + 250 - target[1]) ** 2
        )
        > origin
        for cell in retained
    )


def _landing(
    retained: tuple[tuple[int, int], ...],
) -> tuple[int, int] | None:
    water = next(
        (
            index
            for index, cell in enumerate(retained)
            if native_spawn_tile_blocked(*cell)
        ),
        None,
    )
    if water is None:
        return None
    return next(
        (
            cell
            for cell in retained[water + 1 :]
            if not native_spawn_tile_blocked(*cell)
        ),
        None,
    )


def test_tensor_goal_selection_matches_full_python_y_major_scan_randomized() -> None:
    rng = random.Random(0xA57A)
    cases = [
        (
            (rng.randrange(0, 18_000), rng.randrange(0, 32_000)),
            (rng.randrange(0, 18_000), rng.randrange(0, 32_000)),
            rng.choice((0, 250, 500, 750, 1_000, 2_500, 6_000)),
        )
        for _ in range(2_048)
    ]
    mover = torch.tensor([case[0] for case in cases], dtype=torch.int64)
    target = torch.tensor([case[1] for case in cases], dtype=torch.int64)
    required = torch.tensor([case[2] for case in cases], dtype=torch.int64)

    goal, valid = tensor_route_goal_cells(mover, target, required)
    expected = [_expected_goal(*case) for case in cases]

    assert valid.tolist() == [value is not None for value in expected]
    for actual, reference in zip(goal.tolist(), expected, strict=True):
        assert tuple(actual) == ((-1, -1) if reference is None else reference)


@pytest.mark.parametrize("device", DEVICES)
def test_randomized_ground_routes_match_native_first_discovery_heap(
    device: str,
) -> None:
    # This invokes the intentionally expensive exact heap on cache misses. It
    # is a parity gate, not evidence of production throughput.
    rng = random.Random(0xB12D63)
    batch = 3
    entities = 8
    movers: list[list[tuple[int, int]]] = []
    targets: list[list[tuple[int, int]]] = []
    ranges: list[list[int]] = []
    lanes: list[list[int]] = []
    jumps: list[list[bool]] = []
    for _ in range(batch):
        movers.append(
            [
                (rng.randrange(250, 17_751), rng.randrange(250, 31_751))
                for _ in range(entities)
            ]
        )
        targets.append(
            [
                (rng.randrange(250, 17_751), rng.randrange(250, 31_751))
                for _ in range(entities)
            ]
        )
        ranges.append([rng.choice((500, 750, 1_000, 2_000)) for _ in range(entities)])
        lanes.append([rng.choice((1, 2)) for _ in range(entities)])
        jumps.append([bool(rng.randrange(2)) for _ in range(entities)])
    ids = torch.arange(1, entities + 1).expand(batch, -1).to(device)

    plan = plan_standard_routes(
        entity_id=ids,
        active=torch.ones((batch, entities), dtype=torch.bool, device=device),
        mover_position_units=torch.tensor(movers, device=device),
        target_position_units=torch.tensor(targets, device=device),
        required_range_units=torch.tensor(ranges, device=device),
        lane_id=torch.tensor(lanes, device=device),
        jump_height=torch.tensor(jumps, device=device),
        direct_single_node=torch.zeros(
            (batch, entities), dtype=torch.bool, device=device
        ),
        route_capacity=128,
    )

    assert plan.supported.all().item()
    for row in range(batch):
        for slot in range(entities):
            mover = movers[row][slot]
            target = targets[row][slot]
            goal = _expected_goal(mover, target, ranges[row][slot])
            assert goal is not None
            start = _cell_for_position(Position(mover[0] / 1_000, mover[1] / 1_000))
            full = _cached_standard_grid_route(
                start,
                goal,
                lanes[row][slot],
                jumps[row][slot],
            )
            assert full is not None
            retained = tuple(full[1:])
            count = int(plan.route_count[row, slot].item())
            actual = tuple(
                tuple(value)
                for value in plan.route_cells[row, slot, :count].cpu().tolist()
            )
            assert actual == retained
            assert tuple(plan.goal_cell[row, slot].cpu().tolist()) == goal
            head_cell = retained[0] if retained else goal
            assert plan.head_units[row, slot].cpu().tolist() == [
                head_cell[0] * 500 + 250,
                head_cell[1] * 500 + 250,
            ]
            assert plan.route_moves_backwards[row, slot].item() is (
                _route_moves_backwards(mover, target, retained)
            )
            expected_landing = _landing(retained)
            assert plan.river_landing_valid[row, slot].item() is (
                expected_landing is not None
            )
            if expected_landing is not None:
                assert (
                    tuple(plan.river_landing_cell[row, slot].cpu().tolist())
                    == expected_landing
                )


def test_bridge_river_approaches_both_lanes_and_owners_match_exact_routes() -> None:
    movers = [
        (3_500, 14_250),
        (14_500, 14_250),
        (3_500, 17_750),
        (14_500, 17_750),
        (9_000, 14_750),
        (9_000, 17_250),
    ]
    targets = [
        (3_500, 20_000),
        (14_500, 20_000),
        (3_500, 12_000),
        (14_500, 12_000),
        (9_000, 20_000),
        (9_000, 12_000),
    ]
    lane = [1, 2, 1, 2, 1, 2]
    jump = [False, False, False, False, True, True]
    entity_count = len(movers)
    plan = plan_standard_routes(
        entity_id=torch.arange(1, entity_count + 1)[None, :],
        active=torch.ones((1, entity_count), dtype=torch.bool),
        mover_position_units=torch.tensor([movers]),
        target_position_units=torch.tensor([targets]),
        required_range_units=torch.full((1, entity_count), 500),
        lane_id=torch.tensor([lane]),
        jump_height=torch.tensor([jump]),
        direct_single_node=torch.zeros((1, entity_count), dtype=torch.bool),
    )
    assert plan.supported.all()
    for slot, (mover, target) in enumerate(zip(movers, targets, strict=True)):
        goal = _expected_goal(mover, target, 500)
        assert goal is not None
        route = _cached_standard_grid_route(
            _cell_for_position(Position(mover[0] / 1_000, mover[1] / 1_000)),
            goal,
            lane[slot],
            jump[slot],
        )
        assert route is not None
        expected = tuple(route[1:])
        count = int(plan.route_count[0, slot])
        assert tuple(map(tuple, plan.route_cells[0, slot, :count].tolist())) == expected


def test_flying_hover_profile_retains_exact_single_goal_node() -> None:
    mover = torch.tensor([[[9_000, 10_000], [3_500, 15_750]]])
    target = torch.tensor([[[9_000, 20_000], [14_500, 20_000]]])
    plan = plan_standard_routes(
        entity_id=torch.tensor([[1, 2]]),
        active=torch.tensor([[True, True]]),
        mover_position_units=mover,
        target_position_units=target,
        required_range_units=torch.tensor([[500, 750]]),
        lane_id=torch.tensor([[1, 1]]),
        jump_height=torch.tensor([[False, False]]),
        direct_single_node=torch.tensor([[True, True]]),
    )
    assert plan.supported.all()
    assert plan.route_count.tolist() == [[1, 1]]
    assert torch.equal(plan.route_cells[:, :, 0], plan.goal_cell)
    assert torch.equal(
        plan.head_units,
        plan.goal_cell * HALF_TILE_LOGIC_UNITS + 250,
    )


def test_serialized_hover_uses_python_single_node_semantics_exactly() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    ghost_stats = battle.card_loader.get_card("RoyalGhost")
    knight_stats = battle.card_loader.get_card("Knight")
    assert ghost_stats is not None and knight_stats is not None
    ghost = battle._spawn_entity(Troop, Position(9.0, 12.0), 0, ghost_stats)
    target = battle._spawn_entity(Troop, Position(9.0, 20.0), 1, knight_stats)
    assert isinstance(ghost, Troop) and isinstance(target, Troop)
    ghost.deploy_delay_remaining = 0.0
    target.deploy_delay_remaining = 0.0
    assert ghost._is_hover_unit and not ghost.is_air_unit
    expected = battle.clone()
    expected_ghost = expected.entities[ghost.id]
    expected_target = expected.entities[target.id]
    waypoint = ground_path_waypoint(
        expected,
        expected_ghost,
        expected_target.position,
        target_entity=expected_target,
        backwards_reference=expected_target.position,
    )
    expected_route = tuple(getattr(expected_ghost, "_native_ground_route_cells", []))

    plan = plan_standard_routes(
        entity_id=torch.tensor([[ghost.id]]),
        active=torch.tensor([[True]]),
        mover_position_units=torch.tensor([[[9_000, 12_000]]]),
        target_position_units=torch.tensor([[[9_000, 20_000]]]),
        required_range_units=torch.tensor([[round(float(ghost.range) * 1_000)]]),
        lane_id=torch.tensor([[ghost._native_lane_id]]),
        jump_height=torch.tensor([[False]]),
        direct_single_node=torch.tensor([[True]]),
    )

    assert plan.supported.item()
    assert plan.route_count.item() == len(expected_route) == 1
    assert tuple(plan.route_cells[0, 0, 0].tolist()) == expected_route[0]
    assert plan.head_units[0, 0].tolist() == [
        round(waypoint.x * 1_000),
        round(waypoint.y * 1_000),
    ]


def test_crowded_shared_targets_do_not_create_dynamic_obstacle_routes() -> None:
    # Placed characters/buildings are deliberately absent from LogicPathFinder
    # costs. Many movers sharing one target must still equal independent oracle
    # queries and retain stable source-ID order.
    count = 12
    movers = [
        (2_000 + index * 1_100, 10_000 + (index % 3) * 500) for index in range(count)
    ]
    target = [(9_000, 22_000)] * count
    plan = plan_standard_routes(
        entity_id=torch.arange(100, 100 + count)[None, :],
        active=torch.ones((1, count), dtype=torch.bool),
        mover_position_units=torch.tensor([movers]),
        target_position_units=torch.tensor([target]),
        required_range_units=torch.full((1, count), 750),
        lane_id=torch.tensor([[1 if index < 6 else 2 for index in range(count)]]),
        jump_height=torch.zeros((1, count), dtype=torch.bool),
        direct_single_node=torch.zeros((1, count), dtype=torch.bool),
    )
    assert plan.stable_order.tolist() == [True]
    assert plan.supported.all()
    for slot, mover in enumerate(movers):
        goal = _expected_goal(mover, target[slot], 750)
        assert goal is not None
        route = _cached_standard_grid_route(
            _cell_for_position(Position(mover[0] / 1_000, mover[1] / 1_000)),
            goal,
            1 if slot < 6 else 2,
            False,
        )
        assert route is not None
        actual_count = int(plan.route_count[0, slot])
        assert tuple(
            map(tuple, plan.route_cells[0, slot, :actual_count].tolist())
        ) == tuple(route[1:])


def test_fail_closed_for_unstable_ids_outside_geometry_and_small_route_buffer() -> None:
    common: _PlanArguments = {
        "entity_id": torch.tensor([[1, 2, 3]]),
        "active": torch.tensor([[True, True, True]]),
        "mover_position_units": torch.tensor(
            [[[9_000, 10_000], [-1, 10_000], [9_000, 10_000]]]
        ),
        "target_position_units": torch.tensor(
            [[[9_000, 20_000], [9_000, 20_000], [9_000, 20_000]]]
        ),
        "required_range_units": torch.full((1, 3), 500),
        "lane_id": torch.ones((1, 3), dtype=torch.int64),
        "jump_height": torch.zeros((1, 3), dtype=torch.bool),
        "direct_single_node": torch.zeros((1, 3), dtype=torch.bool),
    }
    unstable_arguments: _PlanArguments = {
        **common,
        "entity_id": torch.tensor([[2, 1, 3]]),
    }
    unstable = plan_standard_routes(**unstable_arguments, route_capacity=128)
    assert unstable.stable_order.tolist() == [False]
    assert unstable.supported.tolist() == [[True, False, True]]

    stable = plan_standard_routes(
        **common,
        route_capacity=4,
    )
    assert stable.supported.tolist() == [[False, False, False]]
    assert stable.route_count.tolist() == [[0, 0, 0]]


def test_lowest_slot_reuse_high_id_remains_supported_with_order_diagnostic() -> None:
    plan = plan_standard_routes(
        # ID 103 reused physical slot zero after IDs 1 and 2 died. The pool's
        # physical order is intentionally no longer monotonic.
        entity_id=torch.tensor([[103, 3, 4]]),
        active=torch.tensor([[True, True, True]]),
        mover_position_units=torch.tensor(
            [[[3_500, 10_000], [9_000, 11_000], [14_500, 12_000]]]
        ),
        target_position_units=torch.tensor(
            [[[3_500, 20_000], [9_000, 21_000], [14_500, 22_000]]]
        ),
        required_range_units=torch.full((1, 3), 500),
        lane_id=torch.tensor([[1, 1, 2]]),
        jump_height=torch.zeros((1, 3), dtype=torch.bool),
        direct_single_node=torch.zeros((1, 3), dtype=torch.bool),
    )
    assert plan.stable_order.tolist() == [False]
    assert plan.supported.all()


@pytest.mark.parametrize("device", DEVICES)
def test_bounded_cache_hit_bypasses_exact_heap_without_changing_plan(
    monkeypatch: pytest.MonkeyPatch,
    device: str,
) -> None:
    from clasher.torch_sim import resident_pathing

    arguments: _PlanArguments = {
        "entity_id": torch.tensor([[1, 2, 3, 4]], device=device),
        "active": torch.ones((1, 4), dtype=torch.bool, device=device),
        "mover_position_units": torch.tensor(
            [
                [
                    [3_500, 10_000],
                    [14_500, 10_000],
                    [3_500, 20_000],
                    [14_500, 20_000],
                ]
            ],
            device=device,
        ),
        "target_position_units": torch.tensor(
            [
                [
                    [3_500, 22_000],
                    [14_500, 22_000],
                    [3_500, 8_000],
                    [14_500, 8_000],
                ]
            ],
            device=device,
        ),
        "required_range_units": torch.full((1, 4), 500, device=device),
        "lane_id": torch.tensor([[1, 2, 1, 2]], device=device),
        "jump_height": torch.tensor([[False, False, True, True]], device=device),
        "direct_single_node": torch.zeros((1, 4), dtype=torch.bool, device=device),
    }
    cache = TensorResidentPathCache.create(
        capacity=64,
        route_capacity=128,
        device=device,
    )
    first = plan_standard_routes(**arguments, cache=cache)
    assert first.supported.all()
    assert int(cache.valid.sum()) == 4

    def forbidden_heap(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("exact heap executed despite a complete cache hit")

    monkeypatch.setattr(resident_pathing, "_native_heap_routes", forbidden_heap)
    second = plan_standard_routes(**arguments, cache=cache)

    assert torch.equal(second.supported, first.supported)
    assert torch.equal(second.goal_cell, first.goal_cell)
    assert torch.equal(second.route_count, first.route_count)
    assert torch.equal(second.route_cells, first.route_cells)
    assert torch.equal(second.head_units, first.head_units)
    assert torch.equal(second.route_moves_backwards, first.route_moves_backwards)
    assert torch.equal(second.river_landing_cell, first.river_landing_cell)


def test_cache_inserts_one_copy_for_duplicate_route_queries() -> None:
    cache = TensorResidentPathCache.create(capacity=8, route_capacity=2, max_probe=8)
    keys = torch.tensor([[1, 9, 1, 0], [1, 9, 1, 0], [2, 9, 1, 0]])
    cells = torch.tensor(
        [
            [[1, 1], [1, 2]],
            [[1, 1], [1, 2]],
            [[2, 1], [2, 2]],
        ]
    )
    inserted = cache.insert_(
        keys,
        cells,
        torch.tensor([2, 2, 2]),
        torch.tensor([True, True, True]),
    )

    assert inserted.tolist() == [True, False, True]
    assert int(cache.valid.sum()) == 2
    lookup = cache.lookup(keys)
    assert lookup.hit.tolist() == [True, True, True]
    assert torch.equal(lookup.route_cells, cells)


def test_mps_fails_closed_before_planner_allocation() -> None:
    with pytest.raises(RuntimeError, match="CPU/CUDA"):
        validate_resident_path_device("mps")
