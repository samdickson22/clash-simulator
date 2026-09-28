import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.kinematics import movement_component_vector_logic_units


@pytest.mark.parametrize("fast_path", [False, True])
def test_ice_golem_negative_movement_matches_native_positions(fast_path):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_ice_golem_negative_movement_15_535_86.json").read_text()
    )
    battle = BattleState(fast_path=fast_path)
    battle.players[0].hand = ["IceGolem"]
    assert battle.deploy_card(0, "IceGolem", Position(*reference["command"]))
    golem = next(e for e in battle.entities.values() if e.card_stats.name == "IceGolemite")
    expected = {f["elapsed_tick"]: f["position"] for f in reference["frames"]}
    for tick in range(1, max(expected) + 1):
        battle.step()
        if tick in expected:
            assert [round(golem.position.x * 1000), round(golem.position.y * 1000)] == expected[tick], tick


@pytest.mark.parametrize("sign", [-1, 1])
def test_native_movement_product_division_truncates_toward_zero(sign):
    # f67fa0-f67fb8 biases negative products by255 before the8-bit shift.
    assert movement_component_vector_logic_units(sign * -249, sign * 750, 52) == (
        sign * -16,
        sign * 49,
    )
