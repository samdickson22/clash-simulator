from __future__ import annotations

import random
import struct
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import numpy as np

from .card_aliases import resolve_card_name
from .differential import _entity_snapshot, canonical_battle_snapshot
from .rust_core import (
    ResidentPreviewTickError,
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


@dataclass(frozen=True, eq=False)
class _GuardIdentity:
    value: Any

    def __hash__(self) -> int:
        return id(self.value)

    def __eq__(self, other: object) -> bool:
        return type(other) is _GuardIdentity and self.value is other.value


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


def _guard_token(value: Any) -> tuple[Any, ...]:
    value_type = type(value)
    if value is None or value_type in (bool, int, str, bytes):
        return ("value", value_type, value)
    if value_type is float:
        return ("float", struct.unpack("<Q", struct.pack("<d", value))[0])
    if value_type is tuple:
        return ("tuple", tuple(_guard_token(item) for item in value))
    if value_type is frozenset:
        return ("frozenset", frozenset(_guard_token(item) for item in value))
    return ("identity", _GuardIdentity(value), value_type)


def _guard_token_matches(expected: tuple[Any, ...], actual: Any) -> bool:
    kind = expected[0]
    if kind == "value":
        return type(actual) is expected[1] and actual == expected[2]
    if kind == "float":
        return type(actual) is float and struct.unpack(
            "<Q", struct.pack("<d", actual)
        )[0] == expected[1]
    if kind == "tuple":
        return type(actual) is tuple and len(actual) == len(expected[1]) and all(
            _guard_token_matches(item, value)
            for item, value in zip(expected[1], actual, strict=True)
        )
    if kind == "frozenset":
        return type(actual) is frozenset and frozenset(
            _guard_token(item) for item in actual
        ) == expected[1]
    return type(actual) is expected[2] and actual is expected[1].value


_ARENA_POSITION_FIELDS = (
    "BLUE_KING_TOWER",
    "BLUE_LEFT_TOWER",
    "BLUE_RIGHT_TOWER",
    "RED_KING_TOWER",
    "RED_LEFT_TOWER",
    "RED_RIGHT_TOWER",
    "LEFT_BRIDGE",
    "RIGHT_BRIDGE",
)


def _arena_geometry_token(arena: Any) -> tuple[Any, ...]:
    return (
        type(arena),
        _guard_token(arena.width),
        _guard_token(arena.height),
        _guard_token(arena.tile_size),
        _guard_token(arena.RIVER_Y1),
        _guard_token(arena.RIVER_Y2),
        _GuardIdentity(arena.BLOCKED_TILES),
        tuple(
            (_guard_token(tile_x), _guard_token(tile_y))
            for tile_x, tile_y in arena.BLOCKED_TILES
        ),
        tuple(
            (
                name,
                _GuardIdentity(position := getattr(arena, name)),
                _guard_token(position.x),
                _guard_token(position.y),
            )
            for name in _ARENA_POSITION_FIELDS
        ),
    )


@dataclass
class _DirectCausalBoundaryGuard:
    entries: list[list[Any]]

    def first_mismatch(self) -> str | None:
        for entry in self.entries:
            kind, path, owner, expected, _static = entry
            if kind == "attrs":
                fields = vars(owner)
                if len(fields) != len(expected):
                    return f"{path}.__dict__ keys"
                for (expected_name, expected_value), (actual_name, actual_value) in zip(
                    expected, fields.items(), strict=True
                ):
                    if actual_name != expected_name:
                        return f"{path}.__dict__ order/presence"
                    if not _guard_token_matches(expected_value, actual_value):
                        return f"{path}.{expected_name}"
            elif kind == "battle_attrs":
                fields = vars(owner)
                actual = (
                    (name, value)
                    for name, value in fields.items()
                    if name not in _DERIVED_BATTLE_CACHE_FIELDS
                )
                for expected_item, actual_item in zip(expected, actual, strict=False):
                    expected_name, expected_value = expected_item
                    actual_name, actual_value = actual_item
                    if actual_name != expected_name:
                        return f"{path}.__dict__ order/presence"
                    if not _guard_token_matches(expected_value, actual_value):
                        return f"{path}.{expected_name}"
                if sum(
                    name not in _DERIVED_BATTLE_CACHE_FIELDS for name in fields
                ) != len(expected):
                    return f"{path}.__dict__ keys"
            elif kind == "dict":
                if len(owner) != len(expected):
                    return f"{path} length"
                for (expected_key, expected_value), (actual_key, actual_value) in zip(
                    expected, owner.items(), strict=True
                ):
                    if not _guard_token_matches(expected_key, actual_key):
                        return f"{path} key/order"
                    if not _guard_token_matches(expected_value, actual_value):
                        return f"{path}[{actual_key!r}]"
            elif kind == "mapping_subset":
                for key, expected_present, expected_value in expected:
                    if (key in owner) != expected_present:
                        return f"{path}[{key!r}] missing"
                    if expected_present and not _guard_token_matches(
                        expected_value, owner[key]
                    ):
                        return f"{path}[{key!r}]"
            elif kind == "sequence":
                if len(owner) != len(expected):
                    return f"{path} length"
                for index, (expected_value, actual_value) in enumerate(
                    zip(expected, owner, strict=True)
                ):
                    if not _guard_token_matches(expected_value, actual_value):
                        return f"{path}[{index}]"
            elif kind == "set":
                if {_guard_token(item) for item in owner} != expected:
                    return f"{path} membership"
            elif kind == "rng":
                if not _guard_token_matches(expected, owner.getstate()):
                    return f"{path} state"
            elif kind == "ndarray":
                shape, strides, dtype, contents = expected
                if (
                    owner.shape != shape
                    or owner.strides != strides
                    or owner.dtype.str != dtype
                    or owner.tobytes(order="A") != contents
                ):
                    return f"{path} values"
            elif kind == "arena_geometry":
                if _arena_geometry_token(owner) != expected:
                    return str(path)
            else:  # pragma: no cover - closed internal entry kinds
                raise AssertionError(f"unknown boundary guard kind {kind!r}")
        return None


def _compile_direct_causal_guard(
    battle: Any,
    entity_registry: dict[int, Any],
    *,
    previous_guard: _DirectCausalBoundaryGuard | None = None,
) -> _DirectCausalBoundaryGuard:
    """Compile direct references/value checks for all non-derived Python state."""

    entries = (
        []
        if previous_guard is None
        else [entry.copy() for entry in previous_guard.entries if entry[4]]
    )
    seen = {id(entry[2]) for entry in entries}

    def add(kind: str, path: str, owner: Any, expected: Any) -> None:
        static = ".card_stats" in path or path.startswith(
            (
                "battle.card_loader._cards[",
                "battle.card_loader._card_definitions[",
            )
        )
        entries.append([kind, path, owner, expected, static])

    def visit(value: Any, path: str, *, battle_root: bool = False) -> None:
        if _guard_token(value)[0] != "identity":
            if type(value) is tuple:
                for index, item in enumerate(value):
                    visit(item, f"{path}[{index}]")
            return
        identity = id(value)
        if identity in seen:
            return
        seen.add(identity)
        if isinstance(value, random.Random):
            add("rng", path, value, _guard_token(value.getstate()))
            return
        if isinstance(value, np.ndarray):
            add(
                "ndarray",
                path,
                value,
                (value.shape, value.strides, value.dtype.str, value.tobytes(order="A")),
            )
            return
        if isinstance(value, dict):
            expected = tuple(
                (_guard_token(key), _guard_token(item))
                for key, item in value.items()
            )
            add("dict", path, value, expected)
            for key, item in value.items():
                visit(key, f"{path}.key")
                visit(item, f"{path}[{key!r}]")
            return
        if isinstance(value, (list, deque)):
            expected = tuple(_guard_token(item) for item in value)
            add("sequence", path, value, expected)
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")
            return
        if isinstance(value, set):
            add("set", path, value, {_guard_token(item) for item in value})
            for item in value:
                visit(item, f"{path}.member")
            return
        if hasattr(value, "__dict__"):
            fields = vars(value)
            expected = tuple(
                (name, _guard_token(item))
                for name, item in fields.items()
                if not (battle_root and name in _DERIVED_BATTLE_CACHE_FIELDS)
            )
            add(
                "battle_attrs" if battle_root else "attrs",
                path,
                value,
                expected,
            )
            for name, item in fields.items():
                if battle_root and name in _DERIVED_BATTLE_CACHE_FIELDS:
                    continue
                if battle_root and name in {"arena", "card_loader"}:
                    continue
                visit(item, f"{path}.{name}")

    visit(battle, "battle", battle_root=True)
    visit(entity_registry, "resident_entity_registry")
    add(
        "arena_geometry",
        "battle.arena resident geometry",
        battle.arena,
        _arena_geometry_token(battle.arena),
    )
    relevant_card_names = {
        str(name)
        for player in battle.players
        for cards in (player.hand, player.deck, player.cycle_queue)
        for name in cards
        if name is not None
    }
    loader_cards = battle.card_loader._cards
    loader_definitions = battle.card_loader._card_definitions
    resolved_card_names = {
        resolve_card_name(name, loader_definitions) for name in relevant_card_names
    }
    loaded_relevant_names = sorted(resolved_card_names & loader_cards.keys())
    expected_loader_cards = tuple(
        (name, True, _guard_token(loader_cards[name]))
        for name in loaded_relevant_names
    )
    add(
        "mapping_subset",
        "battle.card_loader._cards",
        loader_cards,
        expected_loader_cards,
    )
    for name in loaded_relevant_names:
        visit(loader_cards[name], f"battle.card_loader._cards[{name!r}]")

    relevant_definition_ids = {
        id(getattr(loader_cards[name], "_card_def", None))
        for name in loaded_relevant_names
    }
    relevant_definition_names = {
        name
        for name, definition in loader_definitions.items()
        if id(definition) in relevant_definition_ids
    }
    expected_loader_definitions = tuple(
        (name, True, _guard_token(loader_definitions[name]))
        for name in sorted(relevant_definition_names & loader_definitions.keys())
    )
    add(
        "mapping_subset",
        "battle.card_loader._card_definitions",
        loader_definitions,
        expected_loader_definitions,
    )
    for name in sorted(relevant_definition_names & loader_definitions.keys()):
        visit(
            loader_definitions[name],
            f"battle.card_loader._card_definitions[{name!r}]",
        )
    return _DirectCausalBoundaryGuard(entries)


@dataclass(frozen=True)
class RustRuntimeStatus:
    requested_mode: RustBattleMode
    active_mode: RustBattleMode
    fallback_reason: str | None
    shadow_checks: int
    shadow_mismatches: int
    poisoned_reason: str | None = None


@dataclass(frozen=True)
class ResidentDecisionResult:
    action_success: dict[int, bool]
    action_order: tuple[int, int]
    ticks_advanced: int


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
        *,
        action_ingress: bool = False,
        canonical_action_perspective: bool = True,
        python_action_applier: Callable[[Any, int, int], bool] | None = None,
    ) -> None:
        self.battle = battle
        self.requested_mode = RustBattleMode(mode)
        self.active_mode = self.requested_mode
        self.fallback_reason: str | None = None
        self.shadow_checks = 0
        self.shadow_mismatches = 0
        self._resident: ResidentRustBattle | None = None
        self._entity_registry: dict[int, Any] = dict(battle.entities)
        self._on_boundary_guard: _DirectCausalBoundaryGuard | None = None
        self._on_resident_authority: tuple[_GuardIdentity, tuple[Any, ...]] | None = (
            None
        )
        self._on_python_authority: tuple[
            _GuardIdentity,
            type,
            _GuardIdentity,
            type,
        ] | None = None
        self.poisoned_reason: str | None = None
        self._action_ingress = bool(action_ingress)
        self._canonical_action_perspective = bool(canonical_action_perspective)
        self._python_action_applier = python_action_applier

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
        if self._action_ingress:
            if not self._canonical_action_perspective:
                self.active_mode = RustBattleMode.OFF
                self.fallback_reason = (
                    "resident action ingress requires canonical action perspective"
                )
                return
            if (
                self.active_mode is RustBattleMode.SHADOW
                and self._python_action_applier is None
            ):
                raise ValueError(
                    "resident action-ingress shadow mode requires a Python "
                    "action applier"
                )
            try:
                # Both calls are read-only. The native preflight scans the full
                # hand and cycle of both players before generating either legal
                # set, so an episode cannot become unsupported only after a card
                # rotates into hand.
                resident.resident_legal_action_ids(0)
                resident.resident_legal_action_ids(1)
            except RuntimeError as error:
                self.active_mode = RustBattleMode.OFF
                self.fallback_reason = (
                    "resident action ingress rejected the initial episode: "
                    f"{error}"
                )
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
            poisoned_reason=self.poisoned_reason,
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
        guard = self._on_boundary_guard
        guard = _compile_direct_causal_guard(
            self.battle,
            self._entity_registry,
            previous_guard=guard,
        )
        self._on_boundary_guard = guard
        resident = self._resident
        if resident is None:  # pragma: no cover - active runtime invariant
            raise RuntimeError("resident on-mode boundary has no native state")
        self._on_resident_authority = (
            _GuardIdentity(resident),
            ResidentRustBattle.publication_authority_token(resident),
        )
        self._on_python_authority = (
            _GuardIdentity(self.battle),
            type(self.battle),
            _GuardIdentity(self._entity_registry),
            type(self._entity_registry),
        )

    def _assert_on_boundary_unchanged(self) -> None:
        if self.poisoned_reason is not None:
            raise RuntimeError(
                "resident complete-tick runtime is poisoned: "
                f"{self.poisoned_reason}"
            )
        guard = self._on_boundary_guard
        if guard is None:
            raise RuntimeError("resident on-mode boundary checkpoint is missing")
        expected_python_authority = self._on_python_authority
        if (
            expected_python_authority is None
            or self.battle is not expected_python_authority[0].value
            or type(self.battle) is not expected_python_authority[1]
            or self._entity_registry is not expected_python_authority[2].value
            or type(self._entity_registry) is not expected_python_authority[3]
        ):
            raise RuntimeError(
                "resident complete-tick on mode detected external Python state "
                "mutation before advance (path=runtime Python root authority)"
            )
        resident = self._resident
        expected_authority = self._on_resident_authority
        if (
            resident is None
            or expected_authority is None
            or expected_authority[0].value is not resident
            or ResidentRustBattle.publication_authority_token(resident)
            != expected_authority[1]
        ):
            raise RuntimeError(
                "resident complete-tick on mode detected external native state "
                "mutation before advance (path=resident publication authority)"
            )
        mismatch = guard.first_mismatch()
        if mismatch is None:
            return
        raise RuntimeError(
            "resident complete-tick on mode detected external Python state "
            f"mutation before advance (path={mismatch})"
        )

    def _apply_python_joint_actions(
        self,
        action0: int,
        action1: int,
    ) -> tuple[dict[int, bool], tuple[int, int]]:
        applier = self._python_action_applier
        if applier is None:  # pragma: no cover - constructor invariant
            raise RuntimeError("resident shadow action applier is unavailable")
        order = [0, 1]
        self.battle.rng.shuffle(order)
        actions = (action0, action1)
        success: dict[int, bool] = {}
        for player_id in order:
            success[player_id] = bool(
                applier(self.battle, player_id, actions[player_id])
            )
        return success, (order[0], order[1])

    def _assert_shadow_action_result(
        self,
        *,
        python_success: dict[int, bool],
        python_order: tuple[int, int],
        rust_success: dict[int, bool],
        rust_order: tuple[int, int],
    ) -> None:
        if python_order != rust_order:
            self.shadow_mismatches += 1
            raise AssertionError(
                "resident Rust joint-action parity mismatch field=action_order "
                f"expected={python_order!r} actual={rust_order!r}"
            )
        if python_success != rust_success:
            self.shadow_mismatches += 1
            raise AssertionError(
                "resident Rust joint-action parity mismatch field=action_success "
                f"expected={python_success!r} actual={rust_success!r}"
            )

    def apply_joint_actions_and_advance(
        self,
        action0: int,
        action1: int,
        ticks: int,
    ) -> ResidentDecisionResult:
        """Apply canonical 4x18x32 joint action IDs and advance exactly.

        IDs follow ``DiscreteTileActionSpace`` with canonical perspective:
        deployment IDs are slot-major over the 18x32 board, followed by no-op
        and the single ability button. Native action ingress mirrors player 1;
        noncanonical action spaces fail closed during episode initialization.
        """

        if not self._action_ingress:
            raise RuntimeError("resident complete-tick action ingress is not enabled")
        if self.active_mode is RustBattleMode.OFF:
            raise RuntimeError("resident complete-tick action ingress is inactive")

        requested = max(0, int(ticks))
        resident = self._resident
        if resident is None:  # pragma: no cover - constructor invariant
            raise RuntimeError("active Rust runtime has no resident battle")

        if self.active_mode is RustBattleMode.SHADOW:
            self._assert_shadow_parity()
            candidate = resident.fork()
            try:
                rust_success, rust_order = candidate.apply_resident_joint_actions(
                    action0,
                    action1,
                )
            except RuntimeError as error:
                raise RuntimeError(
                    "battle no longer satisfies the resident joint-action contract; "
                    "mid-battle fallback is forbidden"
                ) from error
            python_success, python_order = self._apply_python_joint_actions(
                action0,
                action1,
            )
            self._assert_shadow_action_result(
                python_success=python_success,
                python_order=python_order,
                rust_success=rust_success,
                rust_order=rust_order,
            )
            self._resident = candidate
            self.shadow_checks += 1
            self._assert_shadow_parity()
            advanced = self.advance_ticks(requested)
            return ResidentDecisionResult(
                action_success=python_success,
                action_order=python_order,
                ticks_advanced=advanced,
            )

        self._assert_on_boundary_unchanged()
        try:
            candidate, rust_success, rust_order, rust_advanced = (
                resident.preview_resident_joint_action_interval(
                    action0,
                    action1,
                    requested,
                )
            )
        except ResidentPreviewTickError as error:
            self.poisoned_reason = (
                "post-action complete-tick capability failure: "
                f"{error}"
            )
            raise RuntimeError(
                "resident complete-tick runtime failed after native action "
                "application and is now poisoned; the published battle and "
                "resident root remain unchanged"
            ) from error
        except RuntimeError as error:
            raise RuntimeError(
                "battle no longer satisfies the resident joint-action contract; "
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
        return ResidentDecisionResult(
            action_success={
                player_id: rust_success[player_id] for player_id in rust_order
            },
            action_order=rust_order,
            ticks_advanced=int(rust_advanced),
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
            if advanced and self.battle.fast_path:
                self.battle._refresh_fast_path_caches(
                    trust_target_cache_dirty=True
                )
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
