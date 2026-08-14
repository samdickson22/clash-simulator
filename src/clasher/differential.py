from __future__ import annotations

import base64
import hashlib
import json
import random
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .battle import BattleState
from .card_types import CardDefinition, CardStatsCompat
from .entities import Entity

SNAPSHOT_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class SnapshotDifference:
    path: str
    expected: Any
    actual: Any
    reason: str


@dataclass(frozen=True)
class DifferentialResult:
    ticks_compared: int
    expected_sha256: str
    actual_sha256: str


class BattleParityError(AssertionError):
    def __init__(
        self,
        *,
        scenario: str,
        tick_offset: int,
        difference: SnapshotDifference,
        dump_path: Path | None,
    ) -> None:
        self.scenario = scenario
        self.tick_offset = tick_offset
        self.difference = difference
        self.dump_path = dump_path
        dump_suffix = "" if dump_path is None else f" dump={dump_path}"
        super().__init__(
            f"battle parity mismatch scenario={scenario!r} "
            f"tick_offset={tick_offset} path={difference.path} "
            f"reason={difference.reason}{dump_suffix}"
        )


class BattleAdapter(Protocol):
    """One side of a per-native-tick differential comparison."""

    def advance_one_tick(self) -> None: ...

    def snapshot(self) -> Mapping[str, Any]: ...


@dataclass
class PythonBattleAdapter:
    battle: BattleState
    observable_builder: Callable[[BattleState], Mapping[str, Any]] | None = None

    def advance_one_tick(self) -> None:
        self.battle.step()

    def snapshot(self) -> Mapping[str, Any]:
        return canonical_battle_snapshot(
            self.battle,
            observables=(
                None
                if self.observable_builder is None
                else self.observable_builder(self.battle)
            ),
        )


def _type_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def _float_value(value: float) -> dict[str, str]:
    # float.hex() preserves signed zero, infinities, and every finite binary64
    # value without accepting a tolerance that could hide simulation drift.
    return {"$float": float(value).hex()}


def _sort_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _normalize(
    value: Any,
    *,
    root_entity: Entity | None = None,
) -> Any:
    if value is None or type(value) in {bool, int, str}:
        return value
    if isinstance(value, float):
        return _float_value(value)
    if isinstance(value, np.generic):
        return _normalize(value.item(), root_entity=root_entity)
    if isinstance(value, bytes):
        return {"$bytes": base64.b64encode(value).decode("ascii")}
    if isinstance(value, np.ndarray):
        contiguous = np.ascontiguousarray(value)
        return {
            "$ndarray": {
                "dtype": contiguous.dtype.str,
                "shape": list(contiguous.shape),
                "data": base64.b64encode(contiguous.tobytes()).decode("ascii"),
            }
        }
    if isinstance(value, random.Random):
        return {"$random_state": _normalize(value.getstate())}
    if isinstance(value, Entity) and value is not root_entity:
        return {"$entity_ref": int(value.id)}
    if isinstance(value, CardDefinition):
        # Definitions and their raw normalized game-data graph are frozen and
        # shared. Their identity is represented by the deployable definition.
        return {
            "$card_definition": {
                "id": int(value.id),
                "name": value.name,
                "kind": value.kind,
            }
        }
    if isinstance(value, CardStatsCompat):
        fields = {
            name: _normalize(field_value, root_entity=root_entity)
            for name, field_value in sorted(value.__dict__.items())
            if name not in {"_card_def", "_raw_entry"}
        }
        return {"$object": {"type": _type_name(value), "fields": fields}}
    if isinstance(value, deque):
        return {
            "$deque": {
                "maxlen": value.maxlen,
                "items": [
                    _normalize(item, root_entity=root_entity) for item in value
                ],
            }
        }
    if isinstance(value, tuple):
        return {
            "$tuple": [
                _normalize(item, root_entity=root_entity) for item in value
            ]
        }
    if isinstance(value, list):
        return [
            _normalize(item, root_entity=root_entity) for item in value
        ]
    if isinstance(value, (set, frozenset)):
        items = [
            _normalize(item, root_entity=root_entity) for item in value
        ]
        items.sort(key=_sort_key)
        return {
            "$set": {
                "frozen": isinstance(value, frozenset),
                "items": items,
            }
        }
    if isinstance(value, Mapping):
        items = [
            (
                _normalize(key, root_entity=root_entity),
                _normalize(item, root_entity=root_entity),
            )
            for key, item in value.items()
        ]
        items.sort(key=lambda pair: _sort_key(pair[0]))
        return {"$mapping": [[key, item] for key, item in items]}
    if callable(value):
        return {
            "$callable": (
                f"{getattr(value, '__module__', type(value).__module__)}."
                f"{getattr(value, '__qualname__', type(value).__qualname__)}"
            )
        }
    if hasattr(value, "__dict__"):
        fields = {
            name: _normalize(field_value, root_entity=root_entity)
            for name, field_value in sorted(value.__dict__.items())
            if name != "battle_state"
        }
        return {"$object": {"type": _type_name(value), "fields": fields}}
    raise TypeError(f"unsupported battle snapshot value: {_type_name(value)}")


def _entity_snapshot(entity: Entity) -> Mapping[str, Any]:
    normalized = _normalize(entity, root_entity=entity)
    if not isinstance(normalized, Mapping):  # pragma: no cover - schema guard
        raise TypeError("entity snapshots must be mappings")
    return normalized


@lru_cache(maxsize=8)
def _content_sha256(
    path_text: str,
    size: int,
    modified_ns: int,
) -> str:
    """Return a portable content identity with cheap revision-keyed reuse."""
    del size, modified_ns
    hasher = hashlib.sha256()
    with Path(path_text).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonical_battle_snapshot(
    battle: BattleState,
    *,
    observables: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Capture exact mutable, observable, and future-causal battle state.

    Immutable arena geometry and the frozen card-definition catalog are
    represented by revision metadata. Mutable wrappers, mechanics, scheduled
    effects, RNG state, players, entities, and fast-path caches are encoded in
    full. Entity pointers inside caches become stable entity-ID references.
    """

    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    entity_iteration_order = [int(entity_id) for entity_id in battle.entities]
    excluded = {"arena", "card_loader", "entities", "players", "rng"}
    battle_fields = {
        name: _normalize(value)
        for name, value in sorted(battle.__dict__.items())
        if name not in excluded
    }
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "catalog": {
            "path_name": data_path.name,
            "size": data_stat.st_size,
            "sha256": _content_sha256(
                str(data_path.resolve()),
                data_stat.st_size,
                data_stat.st_mtime_ns,
            ),
        },
        "battle_type": _type_name(battle),
        "battle_fields": battle_fields,
        "rng_state": _normalize(battle.rng.getstate()),
        "players": [_normalize(player) for player in battle.players],
        "entity_iteration_order": entity_iteration_order,
        "entities": [
            _entity_snapshot(entity)
            for entity in battle.entities.values()
        ],
        "observables": _normalize({} if observables is None else observables),
    }


def snapshot_bytes(snapshot: Mapping[str, Any]) -> bytes:
    return json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def snapshot_sha256(snapshot: Mapping[str, Any]) -> str:
    return hashlib.sha256(snapshot_bytes(snapshot)).hexdigest()


def first_snapshot_difference(
    expected: Any,
    actual: Any,
    *,
    path: str = "$",
) -> SnapshotDifference | None:
    if type(expected) is not type(actual):
        return SnapshotDifference(path, expected, actual, "type")
    if isinstance(expected, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)
        if expected_keys != actual_keys:
            return SnapshotDifference(
                path,
                sorted(expected_keys),
                sorted(actual_keys),
                "mapping keys",
            )
        for key in sorted(expected):
            difference = first_snapshot_difference(
                expected[key],
                actual[key],
                path=f"{path}.{key}",
            )
            if difference is not None:
                return difference
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return SnapshotDifference(
                path,
                len(expected),
                len(actual),
                "sequence length",
            )
        for index, (expected_item, actual_item) in enumerate(
            zip(expected, actual, strict=True)
        ):
            difference = first_snapshot_difference(
                expected_item,
                actual_item,
                path=f"{path}[{index}]",
            )
            if difference is not None:
                return difference
        return None
    if expected != actual:
        return SnapshotDifference(path, expected, actual, "value")
    return None


def _write_mismatch_dump(
    dump_directory: Path,
    *,
    scenario: str,
    tick_offset: int,
    initial_snapshot: Mapping[str, Any],
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    difference: SnapshotDifference,
) -> Path:
    dump_directory.mkdir(parents=True, exist_ok=True)
    safe_scenario = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in scenario
    )
    target = dump_directory / (
        f"{safe_scenario}.tick-{tick_offset:06d}.parity-mismatch.json"
    )
    temporary = target.with_suffix(target.suffix + ".tmp")
    payload = {
        "scenario": scenario,
        "tick_offset": tick_offset,
        "difference": {
            "path": difference.path,
            "reason": difference.reason,
            "expected": difference.expected,
            "actual": difference.actual,
        },
        "initial_snapshot": initial_snapshot,
        "expected_snapshot": expected,
        "actual_snapshot": actual,
    }
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(target)
    return target


def run_differential(
    expected: BattleAdapter,
    actual: BattleAdapter,
    *,
    ticks: int,
    scenario: str,
    dump_directory: str | Path | None = None,
) -> DifferentialResult:
    """Advance both adapters in lockstep and fail on the first exact drift."""

    if ticks < 0:
        raise ValueError("ticks must be non-negative")
    dump_root = None if dump_directory is None else Path(dump_directory)
    initial_expected = dict(expected.snapshot())
    initial_actual = dict(actual.snapshot())
    initial_difference = first_snapshot_difference(initial_expected, initial_actual)
    if initial_difference is not None:
        dump_path = (
            None
            if dump_root is None
            else _write_mismatch_dump(
                dump_root,
                scenario=scenario,
                tick_offset=0,
                initial_snapshot=initial_expected,
                expected=initial_expected,
                actual=initial_actual,
                difference=initial_difference,
            )
        )
        raise BattleParityError(
            scenario=scenario,
            tick_offset=0,
            difference=initial_difference,
            dump_path=dump_path,
        )

    expected_hasher = hashlib.sha256(snapshot_bytes(initial_expected))
    actual_hasher = hashlib.sha256(snapshot_bytes(initial_actual))
    for tick_offset in range(1, ticks + 1):
        expected.advance_one_tick()
        actual.advance_one_tick()
        expected_snapshot = dict(expected.snapshot())
        actual_snapshot = dict(actual.snapshot())
        expected_hasher.update(snapshot_bytes(expected_snapshot))
        actual_hasher.update(snapshot_bytes(actual_snapshot))
        difference = first_snapshot_difference(expected_snapshot, actual_snapshot)
        if difference is None:
            continue
        dump_path = (
            None
            if dump_root is None
            else _write_mismatch_dump(
                dump_root,
                scenario=scenario,
                tick_offset=tick_offset,
                initial_snapshot=initial_expected,
                expected=expected_snapshot,
                actual=actual_snapshot,
                difference=difference,
            )
        )
        raise BattleParityError(
            scenario=scenario,
            tick_offset=tick_offset,
            difference=difference,
            dump_path=dump_path,
        )

    return DifferentialResult(
        ticks_compared=ticks,
        expected_sha256=expected_hasher.hexdigest(),
        actual_sha256=actual_hasher.hexdigest(),
    )


def python_lockstep(
    battle: BattleState,
    *,
    ticks: int,
    scenario: str,
    dump_directory: str | Path | None = None,
) -> DifferentialResult:
    """Self-check the harness using two exact clones of one Python battle."""

    expected = battle.clone()
    actual = battle.clone()
    return run_differential(
        PythonBattleAdapter(expected),
        PythonBattleAdapter(actual),
        ticks=ticks,
        scenario=scenario,
        dump_directory=dump_directory,
    )
