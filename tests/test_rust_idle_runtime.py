from __future__ import annotations

import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState, PendingSpellCast
from clasher.differential import canonical_battle_snapshot, snapshot_sha256
from clasher.rust_core import RustBattleMode, rust_core_available
from clasher.rust_runtime import ResidentIdleRuntime

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


@pytest.mark.parametrize("mode", list(RustBattleMode))
def test_idle_runtime_modes_match_complete_python_snapshot(
    mode: RustBattleMode,
) -> None:
    control = BattleState(rng=random.Random(8801))
    candidate = BattleState(rng=random.Random(8801))
    runtime = ResidentIdleRuntime(candidate, mode)

    assert control.fast_forward_idle_ticks(256) == runtime.advance_idle_ticks(256)

    assert snapshot_sha256(canonical_battle_snapshot(candidate)) == (
        snapshot_sha256(canonical_battle_snapshot(control))
    )
    assert runtime.status.shadow_mismatches == 0
    if mode is RustBattleMode.SHADOW:
        assert runtime.status.shadow_checks == 1


def test_rust_allocation_is_reused_across_decision_boundaries() -> None:
    battle = BattleState(rng=random.Random(8802))
    runtime = ResidentIdleRuntime(battle, RustBattleMode.ON)
    resident = runtime.resident
    assert resident is not None

    assert runtime.advance_idle_ticks(8) == 8
    assert runtime.advance_idle_ticks(8) == 8

    assert runtime.resident is resident
    assert not resident.checkpoint_is_current


def test_initial_unsupported_state_falls_back_before_battle_starts() -> None:
    battle = BattleState()
    battle._pending_spell_casts.append(
        PendingSpellCast(1.0, 0, "Arrows", 0, Position(9.0, 16.0))
    )
    runtime = ResidentIdleRuntime(battle, RustBattleMode.ON)

    assert runtime.status.active_mode is RustBattleMode.OFF
    assert runtime.status.fallback_reason == "battle failed the exact idle preflight"
    assert runtime.resident is None


def test_mid_battle_contract_change_fails_closed() -> None:
    battle = BattleState()
    runtime = ResidentIdleRuntime(battle, RustBattleMode.ON)
    battle._pending_spell_casts.append(
        PendingSpellCast(1.0, 0, "Arrows", 0, Position(9.0, 16.0))
    )

    with pytest.raises(RuntimeError, match="mid-battle fallback is forbidden"):
        runtime.advance_idle_ticks(1)


def test_shadow_detects_external_state_drift_before_advancing() -> None:
    battle = BattleState()
    runtime = ResidentIdleRuntime(battle, RustBattleMode.SHADOW)
    battle.players[0].elixir -= 1.0

    with pytest.raises(AssertionError, match="player parity mismatch"):
        runtime.advance_idle_ticks(1)

    assert runtime.status.shadow_checks == 0
    assert runtime.status.shadow_mismatches == 1
