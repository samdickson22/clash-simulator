import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_formation_boundary_15_535_86.json").read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_native_card_formation_deployment_boundary(case, fast_path):
    battle = BattleState(fast_path=fast_path)
    owner = case["owner"]
    battle.players[owner].hand = [case["card"]]
    before = set(battle.entities)
    assert battle.deploy_card(
        owner, case["card"], Position(*(value / 1000 for value in case["xy"]))
    )
    units = [battle.entities[key] for key in sorted(set(battle.entities) - before)]

    def positions():
        return [[round(e.position.x * 1000), round(e.position.y * 1000)] for e in units]

    assert positions() == case["initial_positions"]
    battle.step()
    assert positions() == case["frame1_positions"]


def test_in_battle_summons_do_not_inherit_card_deployment_boundary():
    battle = BattleState()
    before = set(battle.entities)
    battle._spawn_troop(Position(4.5, 14.5), 0, battle.card_loader.get_card("Skeletons"))
    units = [battle.entities[key] for key in set(battle.entities) - before]
    assert max(unit.position.y for unit in units) > 15.0


def test_mirror_ground_formation_uses_card_deployment_boundary():
    battle = BattleState()
    battle.players[0].hand = ["Skeletons", "Mirror"]
    assert battle.deploy_card(0, "Skeletons", Position(4.5, 13.5))
    before = set(battle.entities)
    assert battle.deploy_card(0, "Mirror", Position(4.5, 14.5))
    units = [battle.entities[key] for key in set(battle.entities) - before]
    assert len(units) == 3
    assert max(unit.position.y for unit in units) == 14.5
