from __future__ import annotations

import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rust_core import RustBattleMode, rust_core_available
from clasher.rust_differential import python_resident_semantic_snapshot
from clasher.rust_runtime import ResidentCompleteTickRuntime

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _spawn(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
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
    troop._spawn_hook_pending = False
    troop._spawn_hook_fired = True
    return troop


def test_complete_tick_shadow_reuses_resident_and_stays_exact() -> None:
    battle = BattleState(rng=random.Random(9901))
    _spawn(battle, "Knight", 0, Position(9.0, 14.0))
    _spawn(battle, "Musketeer", 1, Position(9.0, 18.0))
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.SHADOW)
    resident = runtime.resident
    assert resident is not None

    for _ in range(32):
        assert runtime.advance_one_tick()

    assert runtime.resident is resident
    assert runtime.status.shadow_checks == 32
    assert runtime.status.shadow_mismatches == 0


def test_complete_tick_off_keeps_python_authoritative() -> None:
    control = BattleState(rng=random.Random(9902))
    candidate = BattleState(rng=random.Random(9902))
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.OFF)

    control._step_logic_tick(refresh_fast_path_end=False)
    assert runtime.advance_one_tick()

    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    assert runtime.resident is None


def test_complete_tick_unsupported_state_falls_back_before_play() -> None:
    battle = BattleState(rng=random.Random(9903))
    _spawn(battle, "Balloon", 0, Position(9.0, 14.0))
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.SHADOW)

    assert runtime.status.active_mode is RustBattleMode.OFF
    assert runtime.status.fallback_reason == (
        "resident core rejected complete-tick capability"
    )
    assert runtime.resident is None


def test_complete_tick_on_fails_closed_until_publication_exists() -> None:
    battle = BattleState(rng=random.Random(9904))
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)

    assert runtime.status.active_mode is RustBattleMode.OFF
    assert runtime.status.fallback_reason == (
        "resident complete-tick Python publication is not implemented"
    )
    assert runtime.resident is None


def test_complete_tick_shadow_detects_external_drift_before_advance() -> None:
    battle = BattleState(rng=random.Random(9905))
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.SHADOW)
    battle.players[0].elixir -= 1.0

    with pytest.raises(AssertionError, match=r"path=\$\.players\[0\]\.elixir"):
        runtime.advance_one_tick()

    assert runtime.status.shadow_checks == 0
    assert runtime.status.shadow_mismatches == 1
