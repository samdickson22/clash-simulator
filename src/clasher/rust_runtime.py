from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from .differential import _entity_snapshot, canonical_battle_snapshot, snapshot_bytes
from .rust_core import (
    ResidentRustBattle,
    RustBattleMode,
    apply_idle_state,
    compare_idle_state,
    rust_core_available,
)

_DERIVED_BATTLE_CACHE_FIELDS = frozenset(
    {
        "_alive_building_cache_dirty",
        "_alive_buildings",
        "_building_cache_signature",
        "_building_placement_blocked_masks",
        "_cached_tower_alive_flags",
        "_crown_target_entities_by_player",
        "_entity_bucket_entity_count",
        "_entity_bucket_grid",
        "_entity_bucket_grid_height",
        "_entity_bucket_grid_width",
        "_entity_bucket_inverse_cell_size",
        "_entity_bucket_max_dimension",
        "_entity_buckets",
        "_max_target_collision_radius",
        "_max_target_distance_discount_sq",
        "_target_cache_dirty",
        "_target_cache_entity_count",
        "_target_collision_radius",
        "_target_distance_discount_sq",
        "_target_entities",
        "_target_index_by_id",
        "_target_is_air",
        "_target_is_building",
        "_target_is_building_target",
        "_target_is_crown",
        "_target_is_targetable",
        "_target_player",
        "_target_pos_x",
        "_target_pos_y",
        "_target_requires_targetability_check",
        "_target_stealth_until",
        "_tower_tile_mask_world",
        "_troop_placement_blocked_masks",
        "_volatile_target_indices",
    }
)


def _causal_boundary_snapshot(battle: Any) -> dict[str, Any]:
    """Return canonical mutable state without rebuildable engine caches."""

    snapshot = canonical_battle_snapshot(battle)
    battle_fields = snapshot["battle_fields"]
    snapshot["battle_fields"] = {
        name: value
        for name, value in battle_fields.items()
        if name not in _DERIVED_BATTLE_CACHE_FIELDS
    }
    return cast(dict[str, Any], snapshot)


def _registry_boundary_snapshot(
    entity_registry: dict[int, Any],
    active_ids: set[int],
) -> list[dict[str, Any]]:
    return [
        {"id": entity_id, "state": _entity_snapshot(entity)}
        for entity_id, entity in entity_registry.items()
        if entity_id not in active_ids
    ]


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
        return int(rust_advanced)


class ResidentCompleteTickRuntime:
    """Exact off/shadow/on controller for the resident complete-tick boundary.

    Shadow keeps Python authoritative, advances one long-lived resident
    allocation beside it, and compares the complete resident semantic
    projection after every tick. On mode advances an entire integer decision
    interval resident-side and atomically publishes the supported in-place
    Python mirror once at the boundary.
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
        self._entity_registry: dict[int, Any] = dict(battle.entities)
        self._on_boundary_snapshot: dict[str, Any] | None = None
        self._on_boundary_bytes: bytes | None = None
        self.poisoned_reason: str | None = None

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
        self._resident = resident
        self._assert_shadow_parity()
        if self.active_mode is RustBattleMode.ON:
            self._record_on_boundary()

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

    @property
    def entity_registry(self) -> dict[int, Any]:
        """Return the append-only identity registry used by on publication."""

        return self._entity_registry

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
        if expected == actual:
            return
        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - equality fast path invariant
            raise AssertionError("resident snapshots compare unequal without a difference")
        self.shadow_mismatches += 1
        raise AssertionError(
            "resident Rust complete-tick parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )

    def _record_on_boundary(self) -> None:
        snapshot = _causal_boundary_snapshot(self.battle)
        snapshot["resident_entity_registry"] = _registry_boundary_snapshot(
            self._entity_registry,
            set(self.battle.entities),
        )
        self._on_boundary_snapshot = snapshot
        self._on_boundary_bytes = snapshot_bytes(snapshot)

    def _assert_on_boundary_unchanged(self) -> None:
        if self.poisoned_reason is not None:
            raise RuntimeError(
                "resident complete-tick runtime is poisoned: "
                f"{self.poisoned_reason}"
            )
        expected = self._on_boundary_snapshot
        expected_bytes = self._on_boundary_bytes
        if expected is None or expected_bytes is None:
            raise RuntimeError("resident on-mode boundary checkpoint is missing")
        actual = _causal_boundary_snapshot(self.battle)
        actual["resident_entity_registry"] = _registry_boundary_snapshot(
            self._entity_registry,
            set(self.battle.entities),
        )
        if snapshot_bytes(actual) == expected_bytes:
            return
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        detail = "unknown canonical mutation"
        if difference is not None:
            detail = f"path={difference.path} reason={difference.reason}"
        raise RuntimeError(
            "resident complete-tick on mode detected external Python state "
            f"mutation before advance ({detail}); resident action ingress is "
            "not implemented"
        )

    def advance_one_tick(self) -> bool:
        if self.active_mode is RustBattleMode.OFF:
            if self.battle.game_over:
                return False
            self.battle._step_logic_tick(refresh_fast_path_end=False)
            return True
        if self.active_mode is RustBattleMode.ON:
            return self.advance_ticks(1) == 1

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

    def advance_ticks(self, ticks: int) -> int:
        """Advance one integer decision interval and publish once in on mode."""

        requested = max(0, int(ticks))
        if requested == 0:
            return 0
        if self.active_mode is RustBattleMode.OFF:
            return int(self.battle.step_logic_ticks(requested))
        if self.active_mode is RustBattleMode.SHADOW:
            advanced = 0
            for _ in range(requested):
                if not self.advance_one_tick():
                    break
                advanced += 1
            return advanced

        resident = self._resident
        if resident is None:  # pragma: no cover - constructor invariant
            raise RuntimeError("active Rust runtime has no resident battle")
        self._assert_on_boundary_unchanged()
        candidate = resident.fork()
        try:
            rust_advanced = candidate.advance_complete_ticks(requested)
        except RuntimeError as error:
            raise RuntimeError(
                "battle no longer satisfies the resident complete-tick contract; "
                "mid-battle fallback is forbidden"
            ) from error

        from .rust_publication import (
            ResidentPublicationError,
            publish_complete_tick_state,
        )

        try:
            publish_complete_tick_state(
                self.battle,
                candidate,
                prior_resident=resident,
                entity_registry=self._entity_registry,
            )
        except ResidentPublicationError as error:
            self.poisoned_reason = str(error)
            raise RuntimeError(
                "resident complete-tick publication rejected the decision "
                "interval and the runtime is now poisoned; mid-battle "
                "fallback is forbidden"
            ) from error
        self._resident = candidate
        self._record_on_boundary()
        return int(rust_advanced)
