import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

CASES = json.loads(
    (
        Path(__file__).parent / "fixtures/native_timed_defenses_15_535_86.json"
    ).read_text()
)["cases"]


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_timed_defense_matches_completed_native_outcome(case, fast_path):
    battle = BattleState(fast_path=fast_path)
    commands = {c["expected_execution_tick"] - 1: c for c in case["commands"]}
    samples = {s["tick"]: s for s in case["samples"]}
    towers = {
        e.id: e.hitpoints
        for e in battle.entities.values()
        if e.player_id == 1 - case["owner"]
    }
    for _ in range(case["end_tick"]):
        command = commands.get(battle.tick)
        if command:
            battle.players[command["owner"]].hand = [command["name"]]
            assert battle.deploy_card(
                command["owner"], command["name"], Position(*command["xy"])
            )
        battle.step()
        sample = samples.get(battle.tick)
        if sample:
            entity = next(
                e
                for e in battle.entities.values()
                if e.entity_kind in (0, 1) and e.card_stats.name == sample["name"]
            )
            assert entity.hitpoints == sample["hp"]
    assert not any(
        e.entity_kind == 0
        and e.player_id == case["owner"]
        and e.card_stats.name == case["attacker"]
        for e in battle.entities.values()
    )
    damage = sum(towers.values()) - sum(
        battle.entities[i].hitpoints if i in battle.entities else 0 for i in towers
    )
    assert damage == case["native_damage"]
