import os
import sys
from collections import deque

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.obs_cv import CvObservationBuilder


def _prepare_hand(battle: BattleState, player_id: int, cards: list[str]) -> None:
    player = battle.players[player_id]
    player.elixir = 10.0
    player.hand = list(cards[:4])
    player.deck = list(cards[:8] if len(cards) >= 8 else cards + cards)
    player.cycle_queue = deque(player.deck[4:])


def test_cv_observation_shapes_and_visible_hud_only():
    battle = BattleState()
    _prepare_hand(
        battle,
        0,
        ["Knight", "Archers", "Giant", "Minions", "Musketeer", "Fireball", "Zap", "Cannon"],
    )

    builder = CvObservationBuilder(card_vocab=["Knight", "Archers", "Giant", "Minions", "Fireball"])
    obs = builder.build(battle, player_id=0)

    assert obs.board.shape == (builder.BOARD_CHANNELS, 32, 18)
    assert obs.hud.shape[0] == builder.spec.hud_size
    assert np.isfinite(obs.board).all()
    assert np.isfinite(obs.hud).all()

    # HUD scalar block should not contain enemy elixir (only own visible elixir is encoded).
    own_elixir_norm = battle.players[0].elixir / battle.players[0].max_elixir
    enemy_elixir_norm = battle.players[1].elixir / battle.players[1].max_elixir
    assert np.isclose(obs.hud[4], own_elixir_norm)
    assert not np.isclose(obs.hud[4], enemy_elixir_norm)


def test_enemy_hand_changes_do_not_change_cv_observation():
    battle = BattleState()
    _prepare_hand(
        battle,
        0,
        ["Knight", "Archers", "Giant", "Minions", "Musketeer", "Fireball", "Zap", "Cannon"],
    )
    _prepare_hand(
        battle,
        1,
        ["HogRider", "Earthquake", "TheLog", "Firecracker", "Skeletons", "Cannon", "IceSpirit", "Knight"],
    )

    builder = CvObservationBuilder(
        card_vocab=[
            "Knight",
            "Archers",
            "Giant",
            "Minions",
            "Musketeer",
            "Fireball",
            "Zap",
            "Cannon",
            "HogRider",
            "Earthquake",
            "TheLog",
            "Firecracker",
            "Skeletons",
            "IceSpirit",
        ]
    )

    obs_before = builder.build(battle, player_id=0)

    # Mutate hidden enemy hand/cycle info only.
    battle.players[1].hand = ["Golem", "Lightning", "NightWitch", "Tornado"]
    battle.players[1].cycle_queue = deque(["BabyDragon", "BarbarianBarrel", "Lumberjack", "Bowler"])
    obs_after = builder.build(battle, player_id=0)

    np.testing.assert_allclose(obs_before.board, obs_after.board)
    np.testing.assert_allclose(obs_before.hud, obs_after.hud)


def test_entity_planes_reflect_spawned_units():
    battle = BattleState()
    _prepare_hand(
        battle,
        0,
        ["Knight", "Archers", "Giant", "Minions", "Musketeer", "Fireball", "Zap", "Cannon"],
    )
    _prepare_hand(
        battle,
        1,
        ["Knight", "Archers", "Giant", "Minions", "Musketeer", "Fireball", "Zap", "Cannon"],
    )
    assert battle.deploy_card(0, "Knight", Position(9.0, 10.0))
    assert battle.deploy_card(1, "Knight", Position(9.0, 22.0))

    builder = CvObservationBuilder(card_vocab=["Knight", "Archers", "Giant", "Minions", "Fireball"])
    obs = builder.build(battle, player_id=0)

    # Friendly and enemy ground troop channels should contain nonzero activations.
    assert float(obs.board[7].sum()) > 0.0
    assert float(obs.board[8].sum()) > 0.0
