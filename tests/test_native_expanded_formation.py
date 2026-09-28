"""Opened native formation controls after an enemy crown tower falls."""

import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/native_expanded_formation_15_535_86.json"
    ).read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["name"])
def test_formation_uses_expanded_boundary_only_in_destroyed_tower_lane(fast_path, case):
    battle = BattleState(fast_path=fast_path)
    tower = next(
        e
        for e in battle.entities.values()
        if e.player_id == 0 and getattr(e, "_crown_tower_slot", None) == "left"
    )
    tower.take_damage(tower.hitpoints)
    battle.step()
    assert battle.players[0].left_tower_hp == 0
    assert battle.players[0].right_tower_hp > 0
    battle.players[1].hand = ["Goblins"]
    before = set(battle.entities)
    assert battle.deploy_card(1, "Goblins", Position(*case["command_xy"]))
    goblins = [battle.entities[i] for i in sorted(set(battle.entities) - before)]
    assert len(goblins) == 4
    battle.step()
    assert [
        [round(goblins[i].position.x * 1000), round(goblins[i].position.y * 1000)]
        for i in case["observed_spawn_indices"]
    ] == case["frame1_positions"]
