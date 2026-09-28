import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building

CASES = json.loads(
    (
        Path(__file__).parent / "fixtures/native_death_tick_attack_15_535_86.json"
    ).read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", CASES)
def test_native_final_shot_survives_same_interval_lethal_hit(case, fast_path):
    battle = BattleState(fast_path=fast_path)
    commands = {c["expected_execution_tick"] - 1: c for c in case["commands"]}
    samples = {s["tick"]: s for s in case["samples"]}
    towers = {
        e.id: e.hitpoints
        for e in battle.entities.values()
        if e.player_id == 1 - case["owner"]
    }
    for _ in range(1421):
        command = commands.get(battle.tick)
        if command:
            battle.players[command["owner"]].hand = [command["name"]]
            assert battle.deploy_card(
                command["owner"], command["name"], Position(*command["xy"])
            )
        battle.step()
        assert not battle._combat_phase_eligible_ids
        if battle.tick in samples:
            sample = samples[battle.tick]
            hog = next(
                e
                for e in battle.entities.values()
                if e.card_stats and e.card_stats.name == "HogRider"
            )
            assert hog.hitpoints == sample["hog_hp"]
            assert (
                any(
                    isinstance(e, Building) and e.card_stats.name == "Cannon"
                    for e in battle.entities.values()
                )
                == sample["cannon_alive"]
            )
    damage = sum(towers.values()) - sum(
        battle.entities[i].hitpoints if i in battle.entities else 0 for i in towers
    )
    assert damage == case["tower_damage"]
