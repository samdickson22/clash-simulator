import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_deploy_avoidance_15_535_86.json").read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c.get("label", str(c["x"])))
def test_native_deploying_archer_steering_changes_later_hog_avoidance(fast_path, case):
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["seed"]))
    for player, elixir in zip(battle.players, case["elixir"]):
        player.elixir = elixir
    mapping = {}
    names = {26000021: "HogRider", 26000001: "Archers"}
    expected = {r["tick"]: r["bodies"] for r in case["frames"]}
    while battle.tick < max(expected):
        for submitted, owner, card, x, y in case["commands"]:
            if battle.tick != submitted:
                continue
            battle.players[owner].hand = [names[card]]
            before = set(battle.entities)
            assert battle.deploy_card(owner, names[card], Position(x / 1000, y / 1000))
            first_native_id = 5000006 if card == 26000021 else 5000007
            for index, scalar_id in enumerate(sorted(set(battle.entities) - before)):
                mapping[first_native_id + index] = scalar_id
        battle.step()
        if battle.tick not in expected:
            continue
        actual = [
            {"id": native_id, "xy": [round(e.position.x * 1000), round(e.position.y * 1000)], "hp": e.hitpoints}
            for native_id, scalar_id in mapping.items()
            if (e := battle.entities.get(scalar_id)) is not None
        ]
        assert actual == expected[battle.tick], battle.tick


@pytest.mark.parametrize("fast_path", [False, True])
def test_deploying_archer_accumulates_native_steering_before_travel(fast_path):
    # Opened native tick5554: Archer5000140 remains in deployment state4 with
    # avoidance190; Hog5000137 has just moved to3316,19424 with avoidance180.
    boundary = REFERENCE["boundary"]
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle._spawn_unit_at_position(
        Position(*(v / 1000 for v in boundary["hog_xy"])), 0, battle.card_loader.get_card("HogRider"),
        deploy_delay_override=0, snap_to_valid=False,
    )
    hog = max(battle.entities.values(), key=lambda e: e.id)
    battle._spawn_unit_at_position(
        Position(*(v / 1000 for v in boundary["archer_xy"])), 1, battle.card_loader.get_card("Archers"),
        deploy_delay_override=boundary["archer_deploy_ms"] / 1000, snap_to_valid=False,
    )
    archer = max(battle.entities.values(), key=lambda e: e.id)
    hog._movement_target_id = 4
    hog._facing_x_units, hog._facing_y_units = boundary["hog_facing"]
    hog._native_avoidance = boundary["hog_avoidance"]
    archer._facing_x_units, archer._facing_y_units = boundary["archer_facing"]
    if fast_path:
        battle._refresh_fast_path_caches()
    archer._update_native_avoidance(battle)
    assert archer._native_avoidance == boundary["expected_archer_avoidance"]
