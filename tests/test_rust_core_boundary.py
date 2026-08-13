import pytest

from clasher.rust_core import (
    python_consume_state_bytes,
    rust_consume_state_bytes,
    rust_core_available,
    rust_noop_ticks,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust core has not been built into this environment",
)


@pytest.mark.parametrize(
    "payload",
    [b"", b"clasher", bytes(range(256)), b"battle-state" * 4096],
)
def test_rust_state_boundary_matches_python_reference(payload):
    assert rust_consume_state_bytes(payload) == python_consume_state_bytes(payload)


@pytest.mark.parametrize("ticks", [0, 1, 8, 6_000, (1 << 32) - 1])
def test_rust_noop_tick_boundary_round_trips_exactly(ticks):
    assert rust_noop_ticks(ticks) == ticks


@pytest.mark.parametrize("ticks", [-1, 1 << 32])
def test_rust_noop_tick_boundary_rejects_out_of_range_values(ticks):
    with pytest.raises(ValueError):
        rust_noop_ticks(ticks)
