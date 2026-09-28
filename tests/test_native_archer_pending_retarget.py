import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_archer_pending_retarget_15_535_86.json").read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: str(c["center"]))
def test_native_staggered_archers_preserve_hit_across_pending_retarget(fast_path, case):
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["seed"]))
    for player, elixir in zip(battle.players, case["elixir"]):
        player.elixir = elixir
    mapping = {}
    expected = {row["tick"]: row["units"] for row in case["frames"]}
    while battle.tick < max(expected):
        if battle.tick == 100:
            native_id = 5000006
            for owner, card, y in [(0, "IceGolem", 13.5), (0, "Skeletons", 14.5), (1, "Archers", 18.5)]:
                battle.players[owner].hand = [card]
                before = set(battle.entities)
                assert battle.deploy_card(owner, card, Position(case["center"] / 1000, y))
                for identity in sorted(set(battle.entities) - before):
                    mapping[native_id] = identity
                    native_id += 1
        battle.step()
        for row in expected.get(battle.tick, []):
            archer = battle.entities[mapping[row["id"]]]
            target_id = None if row["target"] is None else mapping[row["target"]]
            assert archer.target_id == target_id, battle.tick
            assert archer.attack_cooldown == pytest.approx(row["remaining"]), battle.tick
