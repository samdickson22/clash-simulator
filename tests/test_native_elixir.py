import json
from pathlib import Path

import pytest

from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_elixir_15_535_86.json").read_text()
)


@pytest.mark.parametrize("idle_fast_forward", [False, True])
@pytest.mark.parametrize("frames", REFERENCE["cases"])
def test_native_integer_regeneration_and_phase_boundary(frames, idle_fast_forward):
    battle = BattleState()
    first = frames[0]
    battle.tick = first["tick"]
    battle.time = battle.tick * battle.dt
    battle.players[0].elixir = first["elixir_raw"] / 10000
    for frame in frames[1:]:
        if idle_fast_forward:
            assert battle.fast_forward_idle_ticks(1) == 1
        else:
            battle.step()
        assert battle.tick == frame["tick"]
        assert round(battle.players[0].elixir * 10000) == frame["elixir_raw"]
