from __future__ import annotations

from typing import Final

try:
    from _clasher_rust import (  # type: ignore[import-untyped]
        consume_state_bytes as _consume_state_bytes,
    )
    from _clasher_rust import noop_ticks as _noop_ticks
except ImportError:  # pragma: no cover - depends on optional compiled artifact
    _consume_state_bytes = None
    _noop_ticks = None


FNV_OFFSET_BASIS: Final = 0xCBF29CE484222325
FNV_PRIME: Final = 0x100000001B3
U64_MASK: Final = (1 << 64) - 1


def rust_core_available() -> bool:
    return _noop_ticks is not None and _consume_state_bytes is not None


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
