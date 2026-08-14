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
