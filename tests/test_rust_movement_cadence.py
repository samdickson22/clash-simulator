from __future__ import annotations

import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import first_snapshot_difference
from clasher.rust_core import ResidentRustBattle, rust_core_available
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _ready_giant(battle: BattleState):
    stats = battle.card_loader.get_card("Giant")
    assert stats is not None
    battle._spawn_unit_at_position(Position(9.0, 10.0), 0, stats)
    giant = battle.entities[battle.next_entity_id - 1]
    giant.position = Position(9.0, 10.0)
    giant.deploy_delay_remaining = 0.0
    giant.placement_delay_total = 0.0
    giant.placement_pending = False
    giant._spawn_hook_pending = False
    giant._spawn_hook_fired = True
    return giant


def _assert_semantic_parity(
    battle: BattleState,
    resident: ResidentRustBattle,
) -> None:
    difference = first_snapshot_difference(
        python_resident_semantic_snapshot(battle),
        rust_resident_semantic_snapshot(resident),
    )
    assert difference is None, difference


def test_giant_serialized_footstep_pause_matches_every_complete_tick() -> None:
    battle = BattleState(rng=random.Random(95_200))
    giant = _ready_giant(battle)
    resident = ResidentRustBattle.from_battle(battle)
    positions = [Position(giant.position.x, giant.position.y)]

    for _ in range(15):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)
        positions.append(Position(giant.position.x, giant.position.y))

    assert giant.movement_phase_elapsed_ms == 10
    assert all(positions[index] != positions[index - 1] for index in range(1, 13))
    assert positions[13] == positions[12]
    assert positions[14] == positions[13]
    assert positions[15] != positions[14]


def test_raged_giant_footstep_clock_uses_per_frame_integer_work() -> None:
    battle = BattleState(rng=random.Random(95_220))
    giant = _ready_giant(battle)
    giant.apply_haste(10.0, 1.3, 1.3, 1.3)
    resident = ResidentRustBattle.from_battle(battle)
    positions = [Position(giant.position.x, giant.position.y)]

    for _ in range(12):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)
        positions.append(Position(giant.position.x, giant.position.y))

    assert giant.movement_phase_elapsed_ms == 28
    assert positions[11] == positions[10]
    assert positions[12] != positions[11]


def test_invalid_footstep_clock_rejects_before_mutation() -> None:
    battle = BattleState(rng=random.Random(95_240))
    giant = _ready_giant(battle)
    giant.movement_phase_elapsed_ms = -1
    resident = ResidentRustBattle.from_battle(battle)
    before = rust_resident_semantic_snapshot(resident)

    assert not resident.supports_ground_movement_phase
    with pytest.raises(RuntimeError, match="movement capability"):
        resident.advance_complete_tick()
    assert rust_resident_semantic_snapshot(resident) == before
