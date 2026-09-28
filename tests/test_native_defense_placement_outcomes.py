import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/native_defense_placements_15_535_86.json"
    ).read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_repaired_defense_outcomes_match_fixed_native_controls(case, fast_path):
    battle = BattleState(fast_path=fast_path)
    for _ in range(REFERENCE["decision_tick"]):
        battle.step()
    towers = {e.id: e.hitpoints for e in battle.entities.values() if e.player_id == 1}
    placements = [(0, case["attacker"], Position(3.5, 14.5))]
    if case["placement"] is not None:
        placements.append((1, case["defender"], Position(*case["placement"])))
    for owner, name, position in placements:
        battle.players[owner].hand = [name]
        assert battle.deploy_card(owner, name, position)
    for _ in range(
        case.get("end_tick", REFERENCE["end_tick"]) - REFERENCE["decision_tick"]
    ):
        battle.step()
    damage = sum(towers.values()) - sum(
        battle.entities[i].hitpoints if i in battle.entities else 0 for i in towers
    )
    assert damage == case["native_tower_damage"]
