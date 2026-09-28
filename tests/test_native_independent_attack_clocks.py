import json
from pathlib import Path

import pytest

from clasher.attack_clock import OrdinaryAttackClock

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_independent_attack_clocks_15_535_86.json").read_text()
)


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda case: case["name"])
def test_independent_load_and_hit_work_against_native_trace(case):
    clock = OrdinaryAttackClock(
        hit_interval_ms=case["hit_interval_ms"],
        load_time_ms=case["load_time_ms"],
        **case["initial"],
    )
    for frame in case["frames"]:
        hits = clock.advance(
            frame["elapsed_ms"], frame["hit_work_ms"],
            engaged=frame["engaged"], frozen=frame["frozen"],
        )
        assert hits == frame["expected_hits"], frame["tick"]
        if frame["remove_after"]:
            clock.target_removed()
        assert clock.hit_timeline_ms == frame["expected"]["hit_timeline_ms"], frame["tick"]
        assert clock.load_remaining_ms == frame["expected"]["load_remaining_ms"], frame["tick"]
