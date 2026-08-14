from __future__ import annotations

import random

import pytest

from clasher.battle import BattleState
from clasher.rust_core import (
    ResidentRustBattle,
    compare_resident_rng,
    rust_core_available,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


@pytest.mark.parametrize("seed", [0, 1, 5489, 0xFFFF_FFFF, 0xC1A5_2026])
def test_resident_mt19937_matches_python_mixed_draws(seed: int) -> None:
    battle = BattleState(rng=random.Random(seed))
    expected = random.Random()
    expected.setstate(battle.rng.getstate())
    resident = ResidentRustBattle.from_battle(battle)

    compare_resident_rng(expected, resident)
    for index in range(200):
        if index % 3 == 0:
            assert resident.rng_random().hex() == expected.random().hex()
        else:
            stop = (1, 2, 3, 7, 31, 32, 33, 359, 1000, 65_537)[index % 10]
            assert resident.rng_randrange(stop) == expected.randrange(stop)
        compare_resident_rng(expected, resident)

    # Creating and drawing from the resident core never consumes Python's
    # authoritative RNG in shadow mode.
    assert battle.rng.getstate() != expected.getstate()


def test_resident_randrange_rejects_empty_range_without_rng_drift() -> None:
    battle = BattleState(rng=random.Random(9182))
    resident = ResidentRustBattle.from_battle(battle)
    before = resident.rng_state_bytes()

    with pytest.raises(ValueError, match="stop must be positive"):
        resident.rng_randrange(0)

    assert resident.rng_state_bytes() == before


@pytest.mark.parametrize("seed", [0, 1, 5489, 0xFFFF_FFFF, 0xC1A5_2026])
@pytest.mark.parametrize("length", [1, 2, 3, 7, 32, 33, 359])
def test_resident_choice_index_matches_python(seed: int, length: int) -> None:
    battle = BattleState(rng=random.Random(seed))
    expected = random.Random()
    expected.setstate(battle.rng.getstate())
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(32):
        assert resident.rng_choice_index(length) == expected.choice(range(length))
        compare_resident_rng(expected, resident)


@pytest.mark.parametrize("seed", [0, 1, 5489, 0xFFFF_FFFF, 0xC1A5_2026])
@pytest.mark.parametrize("length", [0, 1, 2, 3, 7, 32, 33, 359])
def test_resident_shuffle_indices_matches_python(seed: int, length: int) -> None:
    battle = BattleState(rng=random.Random(seed))
    expected = random.Random()
    expected.setstate(battle.rng.getstate())
    resident = ResidentRustBattle.from_battle(battle)
    for _ in range(16):
        expected_indices = list(range(length))
        expected.shuffle(expected_indices)
        actual_indices = resident.rng_shuffle_indices(length)
        assert actual_indices == expected_indices
        compare_resident_rng(expected, resident)


def test_resident_choice_rejects_empty_sequence_without_rng_drift() -> None:
    battle = BattleState(rng=random.Random(9182))
    resident = ResidentRustBattle.from_battle(battle)
    before = resident.rng_state_bytes()

    with pytest.raises(IndexError, match="cannot choose from an empty sequence"):
        resident.rng_choice_index(0)

    assert resident.rng_state_bytes() == before


@pytest.mark.parametrize("length", [0, 1])
def test_zero_draw_shuffle_keeps_checkpoint_current(length: int) -> None:
    resident = ResidentRustBattle.from_battle(BattleState(rng=random.Random(7001)))

    assert resident.rng_shuffle_indices(length) == list(range(length))

    assert resident.checkpoint_is_current


def test_resident_rng_getstate_round_trips_gauss_cache_exactly() -> None:
    rng = random.Random(8120)
    rng.gauss(0.0, 1.0)
    assert rng.getstate()[2] is not None
    battle = BattleState(rng=rng)
    resident = ResidentRustBattle.from_battle(battle)

    exported = random.Random()
    exported.setstate(resident.rng_getstate())

    assert exported.getstate() == battle.rng.getstate()
    assert exported.gauss(0.0, 1.0).hex() == battle.rng.gauss(0.0, 1.0).hex()
