from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .rust_core import (
    ResidentRustBattle,
    RustBattleMode,
    apply_idle_state,
    compare_idle_state,
    rust_core_available,
)


@dataclass(frozen=True)
class RustRuntimeStatus:
    requested_mode: RustBattleMode
    active_mode: RustBattleMode
    fallback_reason: str | None
    shadow_checks: int
    shadow_mismatches: int


class ResidentIdleRuntime:
    """Long-lived off/shadow/on controller for the complete idle tick path.

    The Rust allocation is created once. Ordinary ticks stay resident; Python
    sees state only after a requested interval, which is an explicit boundary.
    A battle that fails initialization preflight starts in ``off`` mode. A
    battle that becomes unsupported later fails closed instead of silently
    changing engines mid-battle.
    """

    def __init__(
        self,
        battle: Any,
        mode: RustBattleMode | str = RustBattleMode.OFF,
    ) -> None:
        self.battle = battle
        self.requested_mode = RustBattleMode(mode)
        self.active_mode = self.requested_mode
        self.fallback_reason: str | None = None
        self.shadow_checks = 0
        self.shadow_mismatches = 0
        self._resident: ResidentRustBattle | None = None

        if self.requested_mode is RustBattleMode.OFF:
            return
        if not rust_core_available():
            self.active_mode = RustBattleMode.OFF
            self.fallback_reason = "optional Rust extension is unavailable"
            return
        if not battle.can_fast_forward_idle():
            self.active_mode = RustBattleMode.OFF
            self.fallback_reason = "battle failed the exact idle preflight"
            return
        self._resident = ResidentRustBattle.from_battle(battle)
        if not self._resident.supports_idle_ticks:
            self.active_mode = RustBattleMode.OFF
            self.fallback_reason = "resident core rejected idle capability"
            self._resident = None

    @property
    def status(self) -> RustRuntimeStatus:
        return RustRuntimeStatus(
            requested_mode=self.requested_mode,
            active_mode=self.active_mode,
            fallback_reason=self.fallback_reason,
            shadow_checks=self.shadow_checks,
            shadow_mismatches=self.shadow_mismatches,
        )

    @property
    def resident(self) -> ResidentRustBattle | None:
        return self._resident

    def advance_idle_ticks(self, ticks: int) -> int:
        requested = max(0, int(ticks))
        if self.active_mode is RustBattleMode.OFF:
            return int(self.battle.fast_forward_idle_ticks(requested))

        resident = self._resident
        if resident is None:  # pragma: no cover - constructor invariant
            raise RuntimeError("active Rust runtime has no resident battle")
        if not self.battle.can_fast_forward_idle():
            raise RuntimeError(
                "battle no longer satisfies the resident idle contract; "
                "mid-battle fallback is forbidden"
            )
        try:
            compare_idle_state(self.battle, resident)
        except AssertionError:
            self.shadow_mismatches += 1
            raise

        if self.active_mode is RustBattleMode.SHADOW:
            python_advanced = int(
                self.battle.fast_forward_idle_ticks(requested)
            )
            rust_advanced = resident.advance_idle_ticks(requested)
            self.shadow_checks += 1
            try:
                compare_idle_state(self.battle, resident)
            except AssertionError:
                self.shadow_mismatches += 1
                raise
            if python_advanced != rust_advanced:
                self.shadow_mismatches += 1
                raise AssertionError(
                    "resident Rust idle parity mismatch field=ticks_advanced "
                    f"expected={python_advanced} actual={rust_advanced}"
                )
            return python_advanced

        rust_advanced = resident.advance_idle_ticks(requested)
        apply_idle_state(self.battle, resident)
        compare_idle_state(self.battle, resident)
        return rust_advanced


class ResidentCompleteTickRuntime:
    """Exact off/shadow controller for the resident complete-tick boundary.

    General Rust-on remains fail-closed until the resident core can publish an
    exact Python decision-boundary mirror. Shadow keeps Python authoritative,
    advances one long-lived resident allocation beside it, and compares the
    complete resident semantic projection after every tick.
    """

    def __init__(
        self,
        battle: Any,
        mode: RustBattleMode | str = RustBattleMode.OFF,
    ) -> None:
        self.battle = battle
        self.requested_mode = RustBattleMode(mode)
        self.active_mode = self.requested_mode
        self.fallback_reason: str | None = None
        self.shadow_checks = 0
        self.shadow_mismatches = 0
        self._resident: ResidentRustBattle | None = None

        if self.requested_mode is RustBattleMode.OFF:
            return
        if not rust_core_available():
            self.active_mode = RustBattleMode.OFF
            self.fallback_reason = "optional Rust extension is unavailable"
            return

        resident = ResidentRustBattle.from_battle(battle)
        if not resident.supports_complete_tick:
            self.active_mode = RustBattleMode.OFF
            self.fallback_reason = "resident core rejected complete-tick capability"
            return
        if self.requested_mode is RustBattleMode.ON:
            self.active_mode = RustBattleMode.OFF
            self.fallback_reason = (
                "resident complete-tick Python publication is not implemented"
            )
            return

        self._resident = resident
        self._assert_shadow_parity()

    @property
    def status(self) -> RustRuntimeStatus:
        return RustRuntimeStatus(
            requested_mode=self.requested_mode,
            active_mode=self.active_mode,
            fallback_reason=self.fallback_reason,
            shadow_checks=self.shadow_checks,
            shadow_mismatches=self.shadow_mismatches,
        )

    @property
    def resident(self) -> ResidentRustBattle | None:
        return self._resident

    def _assert_shadow_parity(self) -> None:
        from .differential import first_snapshot_difference
        from .rust_differential import (
            python_resident_semantic_snapshot,
            rust_resident_semantic_snapshot,
        )

        resident = self._resident
        if resident is None:  # pragma: no cover - constructor invariant
            raise RuntimeError("active Rust runtime has no resident battle")
        expected = python_resident_semantic_snapshot(self.battle)
        actual = rust_resident_semantic_snapshot(resident)
        difference = first_snapshot_difference(expected, actual)
        if difference is None:
            return
        self.shadow_mismatches += 1
        raise AssertionError(
            "resident Rust complete-tick parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )

    def advance_one_tick(self) -> bool:
        if self.active_mode is RustBattleMode.OFF:
            if self.battle.game_over:
                return False
            self.battle._step_logic_tick(refresh_fast_path_end=False)
            return True

        resident = self._resident
        if resident is None:  # pragma: no cover - constructor invariant
            raise RuntimeError("active Rust runtime has no resident battle")

        self._assert_shadow_parity()
        python_advanced = not self.battle.game_over
        try:
            rust_advanced = resident.advance_complete_tick()
        except RuntimeError as error:
            raise RuntimeError(
                "battle no longer satisfies the resident complete-tick contract; "
                "mid-battle fallback is forbidden"
            ) from error
        if python_advanced:
            self.battle._step_logic_tick(refresh_fast_path_end=False)
        self.shadow_checks += 1
        self._assert_shadow_parity()
        if python_advanced != rust_advanced:
            self.shadow_mismatches += 1
            raise AssertionError(
                "resident Rust complete-tick parity mismatch "
                "field=tick_advanced "
                f"expected={python_advanced} actual={rust_advanced}"
            )
        return python_advanced
