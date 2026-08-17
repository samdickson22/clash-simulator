from __future__ import annotations

import math
import random
from types import SimpleNamespace

import pytest
import torch

from clasher.arena import Position, TileGrid
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.kinematics import (
    movement_component_vector_logic_units,
    normalized_vector_logic_units,
    trunc_div,
)
from clasher.torch_sim.movement import (
    CollisionBatch,
    accumulate_collision_vectors,
    advance_route_node_mask,
    clamp_native_positions,
    consume_accumulated_movement,
    ground_walkable_mask,
    integer_sqrt_tensor,
    movement_component_vector_units,
    natural_movement_support_mask,
    normalized_vector_units,
    river_boundary_crossing_mask,
    river_jump_start_mask,
    river_jump_step,
    stable_entity_order_mask,
    target_directed_movement_step,
    trunc_div_tensor,
)


def test_randomized_fixed_point_vector_kernels_match_python_oracle() -> None:
    rng = random.Random(0xC1A5)
    cases = [
        (
            rng.randint(-40_000, 40_000),
            rng.randint(-40_000, 40_000),
            rng.randint(0, 800),
        )
        for _ in range(4096)
    ]
    delta = torch.tensor([(x, y) for x, y, _ in cases], dtype=torch.int64)
    work = torch.tensor([work for _, _, work in cases], dtype=torch.int64)

    actual_component = movement_component_vector_units(delta, work)
    actual_normalized = normalized_vector_units(delta, work)
    expected_component = torch.tensor(
        [movement_component_vector_logic_units(x, y, work) for x, y, work in cases],
        dtype=torch.int64,
    )
    expected_normalized = torch.tensor(
        [normalized_vector_logic_units(x, y, work) for x, y, work in cases],
        dtype=torch.int64,
    )
    assert torch.equal(actual_component, expected_component)
    assert torch.equal(actual_normalized, expected_normalized)


def test_integer_sqrt_and_signed_division_are_exact_at_boundaries() -> None:
    values = torch.tensor(
        [0, 1, 2, 3, 4, 8, 9, 15, 16, 17, 31_999**2 - 1, 31_999**2, 31_999**2 + 1],
        dtype=torch.int64,
    )
    assert integer_sqrt_tensor(values).tolist() == [
        math.isqrt(value) for value in values.tolist()
    ]
    numerators = torch.tensor([-1001, -1000, -999, -1, 0, 1, 999, 1000, 1001])
    actual = trunc_div_tensor(numerators, 256)
    assert actual.tolist() == [trunc_div(value, 256) for value in numerators.tolist()]


def test_target_directed_step_matches_native_vector_and_arena_clamp() -> None:
    position = torch.tensor([[250, 250], [17_740, 31_740], [9_000, 10_000]])
    waypoint = torch.tensor([[-5_000, -5_000], [30_000, 40_000], [9_600, 10_800]])
    work = torch.tensor([500, 500, 200])
    result = target_directed_movement_step(
        position,
        waypoint,
        work,
        external_vector_units=torch.tensor([[-100, -100], [100, 100], [0, 0]]),
        supported=torch.tensor([True, True, True]),
    )
    expected_vectors = torch.tensor(
        [
            movement_component_vector_logic_units(-5_250, -5_250, 500),
            movement_component_vector_logic_units(12_260, 8_260, 500),
            movement_component_vector_logic_units(600, 800, 200),
        ]
    )
    assert torch.equal(result.movement_vector_units, expected_vectors)
    assert torch.equal(
        result.position_units,
        clamp_native_positions(
            position
            + expected_vectors
            + torch.tensor([[-100, -100], [100, 100], [0, 0]])
        ),
    )


def test_natural_movement_support_is_fail_closed() -> None:
    base = torch.ones(8, dtype=torch.bool)
    result = natural_movement_support_mask(
        active=base,
        target_valid=base,
        waypoint_valid=torch.tensor([True, False, True, True, True, True, True, True]),
        deployed=torch.tensor([True, True, False, True, True, True, True, True]),
        stunned=torch.tensor([False, False, False, True, False, False, False, False]),
        forced_movement=torch.tensor(
            [False, False, False, False, True, False, False, False]
        ),
        special_movement=torch.tensor(
            [False, False, False, False, False, True, False, False]
        ),
        death_spawn_travel=torch.tensor(
            [False, False, False, False, False, False, True, False]
        ),
        river_jump_active=torch.tensor(
            [False, False, False, False, False, False, False, True]
        ),
    )
    assert result.tolist() == [True, False, False, False, False, False, False, False]
    moved = target_directed_movement_step(
        torch.zeros(8, 2, dtype=torch.int64),
        torch.full((8, 2), 1_000, dtype=torch.int64),
        torch.full((8,), 100, dtype=torch.int64),
        supported=result,
    )
    assert torch.equal(moved.position_units[1:], torch.zeros(7, 2, dtype=torch.int64))


def test_ground_walkability_matches_standard_arena_randomized() -> None:
    rng = random.Random(9917)
    positions = [
        (rng.randint(-500, 18_500), rng.randint(-500, 32_500)) for _ in range(8192)
    ]
    # Include every exact terrain boundary because those touch both tiles.
    positions.extend(
        (x, y)
        for x in range(0, 18_001, 1000)
        for y in (0, 14_000, 15_000, 16_000, 17_000, 31_000)
    )
    tensor = torch.tensor(positions, dtype=torch.int64)
    actual = ground_walkable_mask(tensor).tolist()
    arena = TileGrid()
    expected = [arena.is_walkable(Position(x / 1000, y / 1000)) for x, y in positions]
    assert actual == expected


def test_endpoint_first_river_boundary_and_start_gates() -> None:
    origins = torch.tensor([[9_000, 14_900], [3_500, 14_900], [9_000, 18_000]])
    endpoints = torch.tensor([[9_000, 15_100], [3_500, 15_100], [9_000, 17_900]])
    assert river_boundary_crossing_mask(origins, endpoints).tolist() == [
        True,
        False,
        False,
    ]
    assert river_jump_start_mask(
        endpoints,
        jump_height=torch.tensor([True, True, False]),
        jump_speed_units=torch.tensor([250, 250, 250]),
        landing_valid=torch.tensor([True, True, True]),
    ).tolist() == [True, True, False]


def test_river_jump_step_matches_oracle_component_math_and_snap() -> None:
    position = torch.tensor([[9_250, 14_750], [9_250, 14_750], [9_250, 14_750]])
    target = torch.tensor([[9_750, 17_250], [9_750, 17_250], [9_750, 17_250]])
    speed = torch.tensor([250, 3000, 250])
    result = river_jump_step(
        position,
        target,
        speed,
        active=torch.tensor([True, True, False]),
    )
    expected_first = torch.tensor(movement_component_vector_logic_units(500, 2500, 250))
    assert torch.equal(result.position_units[0], position[0] + expected_first)
    assert torch.equal(result.position_units[1], target[1])
    assert torch.equal(result.position_units[2], position[2])
    assert result.active.tolist() == [True, False, False]
    assert result.finished.tolist() == [False, True, False]
    assert result.supported.tolist() == [True, True, False]


def test_randomized_river_jump_frames_match_live_troop_oracle() -> None:
    rng = random.Random(7719)
    battle = BattleState()
    battle.entities.clear()
    stats = battle.card_loader.get_card("HogRider")
    assert stats is not None
    battle._spawn_unit_at_position(Position(9.0, 14.75), 0, stats)
    hog = next(
        entity for entity in battle.entities.values() if isinstance(entity, Troop)
    )
    hog.deploy_delay_remaining = 0.0
    hog.placement_pending = False
    hog.on_spawn()
    jump_speed = round(float(stats.jump_speed or 0))
    assert jump_speed > 0

    for _ in range(256):
        origin = (rng.randint(250, 17_750), rng.randint(13_000, 18_500))
        target = (rng.randint(250, 17_750), rng.choice((14_750, 17_250)))
        avoidance = rng.randint(-200, 200)
        expected = river_jump_step(
            torch.tensor([origin]),
            torch.tensor([target]),
            torch.tensor([jump_speed]),
            active=torch.tensor([True]),
            avoidance=torch.tensor([avoidance]),
        )
        hog.position = Position(origin[0] / 1000, origin[1] / 1000)
        hog._river_jump_target = Position(target[0] / 1000, target[1] / 1000)
        hog._river_jump_elapsed = 0.0
        hog._river_jump_duration = 1.0
        hog._river_jump_active = True
        hog._river_jump_blocked = False
        hog._special_move_active = True
        hog._special_move_consumed_tick = False
        hog._stun_interrupt_deferred_until_landing = False
        hog._native_avoidance = avoidance
        hog._update_river_jump(battle.dt, battle)
        actual_position = [round(hog.position.x * 1000), round(hog.position.y * 1000)]
        assert actual_position == expected.position_units[0].tolist()
        assert hog._river_jump_active is expected.active.item()


def _reference_collision_vector(
    *,
    own_position: tuple[int, int],
    other_position: tuple[int, int],
    collision_distance: int,
    other_mass: float,
    own_mass: float,
    player: int,
) -> tuple[int, int] | None:
    entity = SimpleNamespace(
        position=Position(own_position[0] / 1000, own_position[1] / 1000),
        player_id=player,
    )
    return BattleState._collision_vector_units(
        entity,
        Position(other_position[0] / 1000, other_position[1] / 1000),
        collision_distance / 1000,
        other_mass,
        own_mass,
    )


def test_randomized_pairwise_collision_accumulation_matches_oracle_order() -> None:
    rng = random.Random(0xB0D1)
    batch_size = 32
    entity_count = 20
    positions = torch.tensor(
        [
            [
                (
                    9_000 + rng.randint(-1_200, 1_200),
                    16_000 + rng.randint(-1_200, 1_200),
                )
                for _ in range(entity_count)
            ]
            for _ in range(batch_size)
        ],
        dtype=torch.int64,
    )
    active = torch.ones(batch_size, entity_count, dtype=torch.bool)
    kind = torch.tensor(
        [
            [0 if index < 15 else 1 for index in range(entity_count)]
            for _ in range(batch_size)
        ]
    )
    player = torch.tensor(
        [[rng.randrange(2) for _ in range(entity_count)] for _ in range(batch_size)]
    )
    radius = torch.tensor(
        [
            [rng.choice((200, 300, 500, 750, 1000)) for _ in range(entity_count)]
            for _ in range(batch_size)
        ]
    )
    mass = torch.tensor(
        [
            [rng.choice((1.0, 2.0, 4.0, 6.0, 12.5, 20.0)) for _ in range(entity_count)]
            for _ in range(batch_size)
        ],
        dtype=torch.float64,
    )
    air = torch.zeros(batch_size, entity_count, dtype=torch.bool)
    zero = torch.zeros_like(active)
    collision_batch = CollisionBatch(
        position_units=positions,
        active=active,
        entity_id=torch.arange(1, entity_count + 1).expand(batch_size, -1),
        entity_kind=kind,
        player_id=player,
        collision_radius_units=radius,
        mass_milliunits=torch.round(mass * 1000).to(torch.int64),
        air_collision=air,
        stunned=zero,
        in_transit=zero,
        river_jump_active=zero,
        death_spawn_travel=zero,
        mega_knight_airborne=zero,
    )
    actual = accumulate_collision_vectors(collision_batch)
    expected_vectors = torch.zeros(batch_size, entity_count, 2, dtype=torch.int64)
    expected_counts = torch.zeros(batch_size, entity_count, dtype=torch.int64)
    for batch_index in range(batch_size):
        for own in range(15):
            own_radius = max(200, int(radius[batch_index, own]))
            for other in range(entity_count):
                if own == other:
                    continue
                if other < 15:
                    distance = own_radius + max(200, int(radius[batch_index, other]))
                    other_mass = float(mass[batch_index, other])
                else:
                    distance = min(own_radius, 500) + int(radius[batch_index, other])
                    other_mass = 20.0
                vector = _reference_collision_vector(
                    own_position=tuple(
                        int(value) for value in positions[batch_index, own]
                    ),
                    other_position=tuple(
                        int(value) for value in positions[batch_index, other]
                    ),
                    collision_distance=distance,
                    other_mass=other_mass,
                    own_mass=float(mass[batch_index, own]),
                    player=int(player[batch_index, own]),
                )
                if vector is not None:
                    expected_vectors[batch_index, own] += torch.tensor(vector)
                    expected_counts[batch_index, own] += 1
    assert torch.equal(actual.accumulated_vector_units, expected_vectors)
    assert torch.equal(actual.contact_count, expected_counts)
    assert int(actual.contact_count.sum()) > 100
    assert actual.supported_batch.all()


def test_knight_golem_collision_fixture_preserves_mass_ratio_and_cap() -> None:
    zero = torch.zeros((1, 2), dtype=torch.bool)
    result = accumulate_collision_vectors(
        CollisionBatch(
            position_units=torch.tensor([[[9_000, 10_000], [9_500, 10_000]]]),
            active=torch.ones((1, 2), dtype=torch.bool),
            entity_id=torch.tensor([[1, 2]]),
            entity_kind=torch.tensor([[0, 0]]),
            player_id=torch.tensor([[0, 0]]),
            collision_radius_units=torch.tensor([[500, 500]]),
            mass_milliunits=torch.tensor([[6_000, 20_000]]),
            air_collision=zero,
            stunned=zero,
            in_transit=zero,
            river_jump_active=zero,
            death_spawn_travel=zero,
            mega_knight_airborne=zero,
        )
    )
    consumed = consume_accumulated_movement(
        result.accumulated_vector_units, result.contact_count
    )
    assert result.accumulated_vector_units.tolist() == [[[-300, 0], [91, 0]]]
    assert consumed.tolist() == [[[-150, 0], [91, 0]]]


def test_collision_contact_average_and_cap_match_entity_begin_tick() -> None:
    vectors = torch.tensor([[900, -600], [100, -99], [0, 0], [-301, 0]])
    counts = torch.tensor([3, 2, 0, 1])
    actual = consume_accumulated_movement(vectors, counts)
    expected = []
    for vector, count in zip(vectors.tolist(), counts.tolist(), strict=True):
        if count == 0:
            expected.append((0, 0))
            continue
        x = trunc_div(vector[0], count)
        y = trunc_div(vector[1], count)
        if x * x + y * y >= 150 * 150 + 1:
            x, y = normalized_vector_logic_units(x, y, 150)
        expected.append((x, y))
    assert actual.tolist() == [list(value) for value in expected]


def test_entity_order_gate_rejects_unsorted_or_duplicate_active_slots() -> None:
    active = torch.tensor(
        [
            [True, True, True, False],
            [True, True, False, False],
            [True, True, False, False],
        ]
    )
    ids = torch.tensor([[1, 2, 3, 0], [2, 1, 0, 0], [1, 1, 0, 0]])
    assert stable_entity_order_mask(active, ids).tolist() == [True, False, False]


@pytest.mark.parametrize(
    ("previous", "current", "waypoint", "expected"),
    [
        ((9_000, 10_000), (9_000, 10_500), (9_000, 11_500), True),
        ((9_000, 10_000), (9_000, 10_400), (9_000, 11_500), False),
        ((10_000, 10_000), (9_000, 10_000), (8_500, 10_000), True),
    ],
)
def test_native_route_node_projection(previous, current, waypoint, expected) -> None:
    actual = advance_route_node_mask(
        torch.tensor([current]),
        torch.tensor([previous]),
        torch.tensor([waypoint]),
        route_head_matches=torch.tensor([True]),
    )
    assert actual.item() is expected


@pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS unavailable")
def test_integer_only_movement_and_collision_kernels_run_on_mps() -> None:
    device = torch.device("mps")
    assert integer_sqrt_tensor(
        torch.tensor([0, 1, 2, 999_999, 1_000_000], device=device)
    ).cpu().tolist() == [0, 1, 1, 999, 1000]
    zero = torch.zeros((1, 2), dtype=torch.bool, device=device)
    collision = accumulate_collision_vectors(
        CollisionBatch(
            position_units=torch.tensor(
                [[[9_000, 10_000], [9_500, 10_000]]], device=device
            ),
            active=torch.ones((1, 2), dtype=torch.bool, device=device),
            entity_id=torch.tensor([[1, 2]], device=device),
            entity_kind=torch.tensor([[0, 0]], device=device),
            player_id=torch.tensor([[0, 0]], device=device),
            collision_radius_units=torch.tensor([[500, 500]], device=device),
            mass_milliunits=torch.tensor([[6_000, 20_000]], device=device),
            air_collision=zero,
            stunned=zero,
            in_transit=zero,
            river_jump_active=zero,
            death_spawn_travel=zero,
            mega_knight_airborne=zero,
        )
    )
    assert collision.accumulated_vector_units.cpu().tolist() == [[[-300, 0], [91, 0]]]
