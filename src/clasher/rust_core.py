from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final

from .differential import (
    SNAPSHOT_SCHEMA_VERSION,
    canonical_battle_snapshot,
    snapshot_bytes,
)

try:
    from _clasher_rust import (  # type: ignore[import-untyped]
        ResidentBattle as _ResidentBattle,
    )
    from _clasher_rust import (  # type: ignore[import-untyped]
        consume_state_bytes as _consume_state_bytes,
    )
    from _clasher_rust import noop_ticks as _noop_ticks  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - depends on optional compiled artifact
    _consume_state_bytes = None
    _noop_ticks = None
    _ResidentBattle = None


FNV_OFFSET_BASIS: Final = 0xCBF29CE484222325
FNV_PRIME: Final = 0x100000001B3
U64_MASK: Final = (1 << 64) - 1


def rust_core_available() -> bool:
    return (
        _noop_ticks is not None
        and _consume_state_bytes is not None
        and _ResidentBattle is not None
    )


def require_rust_core() -> None:
    if not rust_core_available():
        raise RuntimeError(
            "optional Rust core is not installed; run "
            "`maturin develop --manifest-path rust/clasher-core/Cargo.toml`"
        )


def rust_noop_ticks(ticks: int) -> int:
    require_rust_core()
    if ticks < 0 or ticks > (1 << 32) - 1:
        raise ValueError("ticks must fit in u32")
    assert _noop_ticks is not None
    return int(_noop_ticks(ticks))


def python_consume_state_bytes(payload: bytes) -> tuple[int, int]:
    hash_value = FNV_OFFSET_BASIS
    for byte in payload:
        hash_value = ((hash_value ^ byte) * FNV_PRIME) & U64_MASK
    return len(payload), hash_value


def rust_consume_state_bytes(payload: bytes) -> tuple[int, int]:
    require_rust_core()
    assert _consume_state_bytes is not None
    size, hash_value = _consume_state_bytes(payload)
    return int(size), int(hash_value)


class RustBattleMode(str, Enum):
    OFF = "off"
    SHADOW = "shadow"
    ON = "on"


@dataclass(frozen=True)
class BattleClockState:
    tick: int
    time: float
    dt: float
    double_elixir: bool
    triple_elixir: bool
    overtime: bool
    game_over: bool

    def sha256(self) -> str:
        payload = struct.pack(
            "<qdd????",
            self.tick,
            self.time,
            self.dt,
            self.double_elixir,
            self.triple_elixir,
            self.overtime,
            self.game_over,
        )
        return hashlib.sha256(payload).hexdigest()


class ResidentRustBattle:
    """Python owner for one long-lived native battle allocation.

    A complete canonical checkpoint crosses the boundary only at construction
    or an explicit checkpoint replacement. Ordinary phase methods operate on
    resident Rust fields. Complete-tick ``on`` mode remains fail-closed until
    every phase has been ported and the extension advertises that capability.
    """

    def __init__(self, native: Any) -> None:
        self._native = native

    @classmethod
    def from_battle(cls, battle: Any) -> ResidentRustBattle:
        require_rust_core()
        checkpoint = snapshot_bytes(canonical_battle_snapshot(battle))
        assert _ResidentBattle is not None
        native = _ResidentBattle(
            checkpoint,
            tick=int(battle.tick),
            time=float(battle.time),
            dt=float(battle.dt),
            double_elixir=bool(battle.double_elixir),
            triple_elixir=bool(battle.triple_elixir),
            overtime=bool(battle.overtime),
            game_over=bool(battle.game_over),
            double_elixir_start_time=float(battle.double_elixir_start_time),
            overtime_start_time=float(battle.overtime_start_time),
            triple_elixir_start_time=float(battle.triple_elixir_start_time),
        )
        return cls(native)

    @property
    def supports_complete_tick(self) -> bool:
        return bool(self._native.supports_complete_tick())

    def require_complete_tick(self, mode: RustBattleMode | str) -> None:
        parsed_mode = RustBattleMode(mode)
        if parsed_mode is RustBattleMode.ON and not self.supports_complete_tick:
            raise RuntimeError(
                "Rust battle mode 'on' is unavailable: the resident core does "
                "not yet implement every native tick phase"
            )

    def advance_clock_phase(self) -> bool:
        return bool(self._native.advance_clock_phase())

    def clock_state(self) -> BattleClockState:
        values = self._native.clock_state()
        return BattleClockState(*values)

    def clock_sha256(self) -> str:
        return str(self._native.clock_sha256())

    def checkpoint_bytes(self) -> bytes:
        return bytes(self._native.checkpoint_bytes())

    @property
    def checkpoint_sha256(self) -> str:
        return str(self._native.checkpoint_sha256())

    @property
    def checkpoint_size(self) -> int:
        return int(self._native.checkpoint_size())

    @property
    def checkpoint_generation(self) -> int:
        return int(self._native.checkpoint_generation())

    @property
    def schema_version(self) -> int:
        return int(self._native.schema_version())

    def replace_checkpoint(self, payload: bytes) -> None:
        self._native.replace_checkpoint(payload)


def compare_clock_phase(battle: Any, resident: ResidentRustBattle) -> None:
    expected = BattleClockState(
        tick=int(battle.tick),
        time=float(battle.time),
        dt=float(battle.dt),
        double_elixir=bool(battle.double_elixir),
        triple_elixir=bool(battle.triple_elixir),
        overtime=bool(battle.overtime),
        game_over=bool(battle.game_over),
    )
    actual = resident.clock_state()
    if actual == expected and resident.clock_sha256() == expected.sha256():
        return
    for field_name in BattleClockState.__dataclass_fields__:
        expected_value = getattr(expected, field_name)
        actual_value = getattr(actual, field_name)
        if type(expected_value) is not type(actual_value) or expected_value != actual_value:
            raise AssertionError(
                "resident Rust clock parity mismatch "
                f"field={field_name} expected={expected_value!r} "
                f"actual={actual_value!r}"
            )
    raise AssertionError(
        "resident Rust clock hash mismatch "
        f"expected={expected.sha256()} actual={resident.clock_sha256()}"
    )


assert SNAPSHOT_SCHEMA_VERSION == 1
