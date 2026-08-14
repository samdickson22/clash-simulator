from __future__ import annotations

import pytest

from clasher.interaction_matrix import InteractionCase
from clasher.interaction_scenarios import run_rust_interaction_case
from clasher.rust_core import rust_core_available

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("mirrored", [False, True])
def test_supported_interaction_runs_exact_rust_tick_lockstep(
    fast_path: bool,
    mirrored: bool,
) -> None:
    case = InteractionCase(
        index=17,
        kind="1v1",
        team_0=("Knight",),
        team_1=("Musketeer",),
        fast_path=fast_path,
        mirrored=mirrored,
        geometry="center",
        team_0_spawn_reversed=False,
        team_1_spawn_reversed=False,
        event_family="simultaneous_attack",
    )

    _, result = run_rust_interaction_case(case, ticks=32, seed=0xC1A5_0000)

    assert result.ticks_compared == 32
    assert result.expected_sha256 == result.actual_sha256


def test_unsupported_interaction_fails_before_advancing() -> None:
    case = InteractionCase(
        index=18,
        kind="1v1",
        team_0=("Golem",),
        team_1=("Knight",),
        fast_path=False,
        mirrored=False,
        geometry="center",
        team_0_spawn_reversed=False,
        team_1_spawn_reversed=False,
        event_family="ordinary",
    )

    with pytest.raises(RuntimeError, match="cannot execute the complete tick"):
        run_rust_interaction_case(case, ticks=1, seed=0xC1A5_0000)
