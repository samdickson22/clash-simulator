from __future__ import annotations

import hashlib

import pytest

from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot, snapshot_bytes
from clasher.rust_core import (
    ResidentRustBattle,
    RustBattleMode,
    compare_clock_phase,
    compare_player_phase,
    rust_core_available,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _advance_python_clock_phase(battle: BattleState) -> None:
    if battle.game_over:
        return
    battle.time += battle.dt
    battle.tick += 1
    battle._update_battle_phases()


def _advance_python_player_phase(battle: BattleState) -> None:
    base_regen = 2.8
    if battle.triple_elixir:
        base_regen = 0.93
    elif battle.double_elixir:
        base_regen = 1.4
    for player in battle.players:
        player.regenerate_elixir(battle.dt, base_regen)
        player.tick_card_refill(
            battle._next_card_refill_cooldown_ms(),
            round(battle.dt * 1000.0),
        )


def test_resident_checkpoint_round_trip_is_exact() -> None:
    battle = BattleState(rng=__import__("random").Random(721))
    expected = snapshot_bytes(canonical_battle_snapshot(battle))

    resident = ResidentRustBattle.from_battle(battle)

    assert resident.schema_version == 1
    assert resident.checkpoint_bytes() == expected
    assert resident.checkpoint_size == len(expected)
    assert resident.checkpoint_sha256 == hashlib.sha256(expected).hexdigest()
    assert resident.checkpoint_generation == 0


def test_explicit_checkpoint_replace_is_exact_and_counted() -> None:
    first = BattleState(rng=__import__("random").Random(722))
    resident = ResidentRustBattle.from_battle(first)
    second = BattleState(rng=__import__("random").Random(723))
    second.step_logic_ticks(2)
    replacement = snapshot_bytes(canonical_battle_snapshot(second))

    resident.replace_checkpoint(replacement)

    assert resident.checkpoint_bytes() == replacement
    assert resident.checkpoint_sha256 == hashlib.sha256(replacement).hexdigest()
    assert resident.checkpoint_generation == 1


def test_resident_checkpoint_rejects_invalid_or_unknown_schema() -> None:
    battle = BattleState()
    resident = ResidentRustBattle.from_battle(battle)

    with pytest.raises(ValueError, match="invalid battle checkpoint"):
        resident.replace_checkpoint(b"not-json")
    with pytest.raises(ValueError, match="unsupported battle checkpoint schema"):
        resident.replace_checkpoint(b'{"schema_version":2}')


@pytest.mark.parametrize(
    ("start_time", "ticks"),
    [
        (0.0, 5),
        (119.9, 4),
        (179.9, 4),
        (239.9, 4),
    ],
)
def test_clock_phase_matches_python_at_timer_boundaries(
    start_time: float,
    ticks: int,
) -> None:
    battle = BattleState()
    battle.time = start_time
    battle.tick = round(start_time / battle.dt)
    battle._update_battle_phases()
    resident = ResidentRustBattle.from_battle(battle)

    compare_clock_phase(battle, resident)
    for _ in range(ticks):
        assert resident.advance_clock_phase()
        _advance_python_clock_phase(battle)
        compare_clock_phase(battle, resident)


def test_clock_phase_stops_exactly_when_game_is_over() -> None:
    battle = BattleState()
    battle.game_over = True
    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.advance_clock_phase()
    _advance_python_clock_phase(battle)
    compare_clock_phase(battle, resident)


def test_on_mode_fails_closed_until_complete_tick_is_supported() -> None:
    resident = ResidentRustBattle.from_battle(BattleState())

    resident.require_complete_tick(RustBattleMode.OFF)
    resident.require_complete_tick(RustBattleMode.SHADOW)
    with pytest.raises(RuntimeError, match="does not yet implement every"):
        resident.require_complete_tick(RustBattleMode.ON)


@pytest.mark.parametrize("start_time", [0.0, 119.9, 179.9, 239.9, 299.9])
def test_player_phase_matches_elixir_and_refill_boundaries(start_time: float) -> None:
    battle = BattleState()
    battle.time = start_time
    battle.tick = round(start_time / battle.dt)
    battle._update_battle_phases()
    for player in battle.players:
        player.elixir = 9.95
        player.hand[0] = None
        player.hand[2] = None
        player.next_card_refill_cooldown_ms = 50
    resident = ResidentRustBattle.from_battle(battle)

    compare_player_phase(battle, resident)
    for _ in range(25):
        assert resident.advance_clock_phase()
        _advance_python_clock_phase(battle)
        resident.advance_player_phase()
        _advance_python_player_phase(battle)
        compare_clock_phase(battle, resident)
        compare_player_phase(battle, resident)


def test_player_phase_preserves_lowest_empty_slot_and_queue_order() -> None:
    battle = BattleState()
    first = battle.players[0]
    first.hand = [None, "Archer", None, "Minions"]
    first.cycle_queue.clear()
    first.cycle_queue.extend(["Musketeer", "Knight", "Wizard"])
    first.next_card_refill_cooldown_ms = 0
    second = battle.players[1]
    second.next_card_refill_cooldown_ms = 125
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.advance_clock_phase()
    _advance_python_clock_phase(battle)
    resident.advance_player_phase()
    _advance_python_player_phase(battle)

    compare_player_phase(battle, resident)
    assert resident.player_states()[0].hand == (
        "Musketeer",
        "Archer",
        None,
        "Minions",
    )
    assert resident.player_states()[0].cycle_queue == ("Knight", "Wizard")
