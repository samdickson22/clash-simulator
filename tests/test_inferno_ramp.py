import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Building, Troop


def test_inferno_tower_ramp_resets_on_retarget():
    battle = BattleState()
    p0 = battle.players[0]
    p1 = battle.players[1]
    p0.elixir = 20.0
    p1.elixir = 20.0
    p0.hand = ["InfernoTower"]
    p0.deck = ["InfernoTower"]
    p0.cycle_queue.clear()
    p1.hand = ["Giant", "Giant"]
    p1.deck = ["Giant", "Giant"]
    p1.cycle_queue.clear()

    assert battle.deploy_card(0, "InfernoTower", Position(9.0, 14.0))
    assert battle.deploy_card(1, "Giant", Position(9.0, 20.0))

    inferno = next(
        e for e in battle.entities.values()
        if isinstance(e, Building) and e.player_id == 0 and e.card_stats.name == "InfernoTower"
    )
    # Let inferno lock target long enough to ramp.
    for _ in range(220):
        battle.step()
    ramped_damage = inferno.damage
    assert ramped_damage > 100

    # Kill current target, force retarget.
    first_target = battle.entities.get(inferno.target_id)
    assert isinstance(first_target, Troop)
    first_target.take_damage(first_target.hitpoints)
    battle.step()
    assert battle.deploy_card(1, "Giant", Position(9.0, 20.0))

    # Within first few frames after retarget, damage should reset near base stage.
    for _ in range(5):
        battle.step()
    assert inferno.damage < ramped_damage
