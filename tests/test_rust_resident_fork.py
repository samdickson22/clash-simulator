from __future__ import annotations

import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rust_core import ResidentRustBattle, rust_core_available

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _battle_with_modifier() -> BattleState:
    battle = BattleState(rng=random.Random(992_771))
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(Position(8.0, 14.0), 0, stats)
    troop = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    troop.apply_slow(0.5, 0.7, source_kind="fork-test")
    return battle


def _resident_state(resident: ResidentRustBattle) -> tuple[bytes, ...]:
    return (
        resident.entity_state_bytes(),
        resident.modifier_state_bytes(),
        resident.rng_state_bytes(),
        resident.idle_sha256().encode("ascii"),
    )


def test_native_fork_is_exact_at_current_resident_state() -> None:
    root = ResidentRustBattle.from_battle(_battle_with_modifier())
    root.advance_clock_phase()
    root.advance_player_phase()
    root.advance_modifier_phase()
    root.rng_randrange(359)

    clone = root.fork()

    assert clone is not root
    assert _resident_state(clone) == _resident_state(root)
    assert clone.checkpoint_is_current == root.checkpoint_is_current == False


def test_native_fork_mutation_does_not_change_root_or_sibling() -> None:
    root = ResidentRustBattle.from_battle(_battle_with_modifier())
    first = root.fork()
    second = root.fork()
    root_before = _resident_state(root)
    second_before = _resident_state(second)

    first.advance_clock_phase()
    first.advance_player_phase()
    first.advance_modifier_phase()
    first.rng_random()

    assert _resident_state(root) == root_before
    assert _resident_state(second) == second_before
    assert _resident_state(first) != root_before


def test_native_forks_consume_identical_rng_traces_independently() -> None:
    root = ResidentRustBattle.from_battle(_battle_with_modifier())
    first = root.fork()
    second = root.fork()

    first_trace = [first.rng_randrange(65_537) for _ in range(128)]
    second_trace = [second.rng_randrange(65_537) for _ in range(128)]

    assert first_trace == second_trace
    assert first.rng_state_bytes() == second.rng_state_bytes()
    assert root.rng_state_bytes() != first.rng_state_bytes()
