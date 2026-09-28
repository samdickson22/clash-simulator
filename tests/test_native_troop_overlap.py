import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_observation import exact_public_observation
from clasher.rl.structured_obs import StructuredObservationBuilder

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_troop_overlap_15_535_86.json").read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_native_ground_troop_anchor_and_masks(case, fast_path):
    battle = BattleState(fast_path=fast_path)
    owner, name = case["owner"], case["name"]
    battle.players[owner].elixir = 10
    battle.players[owner].hand = ["Tesla"]
    assert battle.deploy_card(owner, "Tesla", Position(*case["building"]))
    for _ in range(case.get("wait_ticks", 21)):
        battle.step()
    battle.players[owner].hand = [name]
    x, y = case["command"]
    if x % 1 == .5 and y % 1 == .5:
        space = DiscreteTileActionSpace()
        action = space.encode_action(0, int(x), int(y), owner)
        assert space.legal_action_mask(battle, owner, fast_path=False)[action]
        assert space.legal_action_mask(battle, owner, fast_path=True)[action]
        builder = StructuredObservationBuilder(
            card_vocab=sorted({"Tesla", *(c["name"] for c in REFERENCE["cases"])})
        )
        observation = PublicActionMaskInput.from_confidence_observation(
            exact_public_observation(builder.build_actor(battle, owner))
        )
        assert PublicActionMaskBuilder(builder).build(observation)[action]
    assert battle.deploy_card(owner, name, Position(x, y))
    battle.step()
    positions = [
        [round(e.position.x * 1000), round(e.position.y * 1000)]
        for e in battle.entities.values() if isinstance(e, Troop)
    ]
    assert positions == case["expected"]
