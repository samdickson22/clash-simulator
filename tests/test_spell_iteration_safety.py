from collections import deque

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop


def _set_hand(battle: BattleState, player_id: int, cards: list[str], elixir: float = 10.0) -> None:
    player = battle.players[player_id]
    player.elixir = elixir
    player.hand = list(cards[:4])
    player.deck = list(cards[:8] if len(cards) >= 8 else cards + cards)
    player.cycle_queue = deque(player.deck[4:])


def test_direct_damage_spell_safe_when_target_death_spawns():
    battle = BattleState()
    _set_hand(
        battle,
        0,
        ["Zap", "Knight", "Archers", "Giant", "Minions", "Musketeer", "Fireball", "Cannon"],
    )
    _set_hand(
        battle,
        1,
        ["Balloon", "Knight", "Archers", "Giant", "Minions", "Musketeer", "Fireball", "Cannon"],
    )

    target_pos = Position(9.0, 22.0)
    assert battle.deploy_card(1, "Balloon", target_pos)

    balloon = next(
        e
        for e in battle.entities.values()
        if isinstance(e, Troop) and getattr(getattr(e, "card_stats", None), "name", "") == "Balloon"
    )
    # Force lethal direct-damage path so death mechanics can mutate entity dict while spell resolves.
    balloon.hitpoints = 1

    assert battle.deploy_card(0, "Zap", Position(9.0, 22.0))
    battle.step()

    # Regression assertion: no RuntimeError from dict-size mutation during spell iteration.
    assert not balloon.is_alive
