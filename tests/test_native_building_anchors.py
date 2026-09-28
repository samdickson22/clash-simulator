import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/native_building_anchors_15_535_86.json"
    ).read_text()
)

BANK_REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_bank_building_anchors_15_535_86.json").read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", BANK_REFERENCE["cases"])
def test_building_footprint_fallback_matches_native_bank_and_edge(case, fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.players[case["owner"]].hand = [case["name"]]
    battle.players[case["owner"]].elixir = 10
    assert battle.deploy_card(case["owner"], case["name"], Position(*case["requested"]))
    building = next(e for e in battle.entities.values() if e.card_stats.name == case["name"])
    assert [building.position.x, building.position.y] == case["expected"]


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_building_placement_matches_native_capture(case, fast_path):
    battle = BattleState(fast_path=fast_path)
    player = battle.players[case["owner"]]
    player.hand = [case["card"]]
    player.elixir = 10
    command = Position(*(v / 1000 for v in case["command_xy"]))
    assert battle.deploy_card(case["owner"], case["card"], command)
    building = next(
        e for e in battle.entities.values() if e.card_stats.name == case["card"]
    )
    assert [
        round(building.position.x * 1000),
        round(building.position.y * 1000),
    ] == case["native_xy"]
    assert [round(command.x * 1000), round(command.y * 1000)] == case["command_xy"]


@pytest.mark.parametrize("owner", [0, 1])
@pytest.mark.parametrize("name", ["Tesla", "Cannon", "Xbow"])
def test_public_building_mask_is_sound_after_world_anchor_resolution(owner, name):
    import numpy as np

    from clasher.rl.action_space import DiscreteTileActionSpace
    from clasher.rl.public_action_mask import (
        PublicActionMaskBuilder,
        PublicActionMaskInput,
    )
    from clasher.rl.public_observation import exact_public_observation
    from clasher.rl.structured_obs import StructuredObservationBuilder

    battle = BattleState(fast_path=True)
    player = battle.players[owner]
    player.elixir = 10
    player.hand = ["Cannon"]
    assert battle.deploy_card(
        owner, "Cannon", Position(9.5, 10.5 if owner == 0 else 21.5)
    )
    player.elixir = 10
    player.hand = [name]
    builder = StructuredObservationBuilder(card_vocab=["Tesla", "Cannon", "Xbow"])
    view = PublicActionMaskInput.from_confidence_observation(
        exact_public_observation(builder.build_actor(battle, owner))
    )
    public = PublicActionMaskBuilder(builder).build(view)
    actions = DiscreteTileActionSpace()
    scalar = actions.legal_action_mask(battle, owner, fast_path=False)
    fast = actions.legal_action_mask(battle, owner, fast_path=True)
    np.testing.assert_array_equal(scalar, fast)
    assert public[: actions.no_op_action].any()
    assert not np.any(public & ~scalar)
