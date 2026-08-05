from collections import deque

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
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

    builder = CvObservationBuilder(
        card_vocab=["Knight", "Archers", "Giant", "Minions", "Musketeer", "Fireball"]
    )
    obs = builder.build(battle, player_id=0)

    assert obs.board.shape == (builder.BOARD_CHANNELS, 32, 18)
    assert obs.hud.shape[0] == builder.spec.hud_size
    assert np.all(obs.board[1, 15:17, :] == 1.0)
    assert np.isfinite(obs.board).all()
    assert np.isfinite(obs.hud).all()
    # Deck-facing aliases such as Archers must remain present in the hand
    # vocabulary instead of disappearing after internal-name normalization.
    archers_slot_offset = 12 + len(builder.card_vocab)
    assert obs.hud[archers_slot_offset + builder.card_vocab.index("Archers")] == 1.0
    next_slot_offset = 12 + 4 * len(builder.card_vocab)
    next_card = battle.players[0].cycle_queue[0]
    assert obs.hud[next_slot_offset + builder.card_vocab.index(next_card)] == 1.0

    # HUD scalar block should not contain enemy elixir (only own visible elixir is encoded).
    own_elixir_norm = battle.players[0].elixir / battle.players[0].max_elixir
    enemy_elixir_norm = battle.players[1].elixir / battle.players[1].max_elixir
    assert np.isclose(obs.hud[4], own_elixir_norm)
    assert not np.isclose(obs.hud[4], enemy_elixir_norm)


def test_canonical_observation_rotates_continuous_positions_before_rasterizing():
    builder = CvObservationBuilder(card_vocab=["Knight"])

    assert builder._position_to_canonical_tile(
        Position(9.0, 22.0),
        player_id=1,
    ) == (9, 10)
    assert builder._position_to_canonical_tile(
        Position(8.999, 21.999),
        player_id=1,
    ) == (9, 10)


def test_symmetric_initial_battle_has_identical_canonical_player_views():
    battle = BattleState()
    builder = CvObservationBuilder(card_vocab=["Knight"])

    blue = builder.build(battle, player_id=0)
    red = builder.build(battle, player_id=1)

    np.testing.assert_array_equal(blue.board, red.board)
    np.testing.assert_array_equal(blue.hud, red.hud)


def test_hud_crowns_are_earned_from_enemy_towers():
    battle = BattleState()
    battle.players[1].left_tower_hp = 0.0
    builder = CvObservationBuilder(card_vocab=["Knight"])

    blue = builder.build(battle, player_id=0)
    red = builder.build(battle, player_id=1)

    assert np.isclose(blue.hud[5], 1.0 / 3.0)
    assert blue.hud[6] == 0.0
    assert red.hud[5] == 0.0
    assert np.isclose(red.hud[6], 1.0 / 3.0)


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
    pending = builder.build(battle, player_id=0)

    # Deployment is public immediately, while the progress planes distinguish
    # units that cannot act or be targeted yet.
    assert float(pending.board[7].sum()) > 0.0
    assert float(pending.board[8].sum()) > 0.0
    assert float(pending.board[21].sum()) > 0.0
    assert float(pending.board[22].sum()) > 0.0

    for _ in range(31):
        battle.step()
    obs = builder.build(battle, player_id=0)

    # Friendly and enemy ground troop channels should contain nonzero activations.
    assert float(obs.board[7].sum()) > 0.0
    assert float(obs.board[8].sum()) > 0.0
    assert float(obs.board[21].sum()) == 0.0
    assert float(obs.board[22].sum()) == 0.0


def test_visual_state_marks_public_cloak_and_encodes_retracted_tesla():
    battle = BattleState()
    bandit_stats = battle.card_loader.get_card("Bandit")
    ghost_stats = battle.card_loader.get_card("RoyalGhost")
    tesla_stats = battle.card_loader.get_card("Tesla")
    assert bandit_stats is not None and ghost_stats is not None and tesla_stats is not None

    battle._spawn_troop(Position(7.0, 10.0), 0, bandit_stats)
    own_bandit = battle.entities[max(battle.entities)]
    own_bandit.deploy_delay_remaining = 0.0
    own_bandit.placement_pending = False
    own_bandit._special_move_active = True
    battle._spawn_troop(Position(11.0, 22.0), 1, bandit_stats)
    enemy_bandit = battle.entities[max(battle.entities)]
    enemy_bandit.deploy_delay_remaining = 0.0
    enemy_bandit.placement_pending = False
    enemy_bandit._special_move_active = True

    battle._spawn_troop(Position(8.0, 11.0), 0, ghost_stats)
    own_ghost = battle.entities[max(battle.entities)]
    own_ghost.deploy_delay_remaining = 0.0
    own_ghost.placement_pending = False
    own_ghost._stealth_until = 2**31 - 1
    battle._spawn_troop(Position(10.0, 21.0), 1, ghost_stats)
    enemy_ghost = battle.entities[max(battle.entities)]
    enemy_ghost.deploy_delay_remaining = 0.0
    enemy_ghost.placement_pending = False
    enemy_ghost._stealth_until = 2**31 - 1

    enemy_tesla = battle._spawn_entity(Building, Position(9.0, 20.0), 1, tesla_stats)
    enemy_tesla.deploy_delay_remaining = 0.0
    enemy_tesla.placement_pending = False
    enemy_tesla._hidden_building = True

    obs = CvObservationBuilder(card_vocab=["Bandit", "RoyalGhost", "Tesla"]).build(battle, player_id=0)

    assert obs.board[7, 10, 7] > 0.0
    assert obs.board[8, 22, 11] > 0.0
    assert obs.board[7, 11, 8] > 0.0
    assert obs.board[8, 21, 10] > 0.0
    assert obs.board[31, 11, 8] == 1.0
    assert obs.board[32, 21, 10] == 1.0
    assert obs.board[6, 20, 9] > 0.0
    assert obs.board[16, 20, 9] > 0.0
    assert obs.board[20, 20, 9] == 1.0

    owner_obs = CvObservationBuilder(
        card_vocab=["Bandit", "RoyalGhost", "Tesla"]
    ).build(battle, player_id=1)
    # Rotate the continuous world point (9.0, 20.0) first, yielding
    # canonical point (9.0, 12.0), and only then choose its raster cell.
    assert owner_obs.board[5, 12, 9] > 0.0
    assert owner_obs.board[19, 12, 9] == 1.0


def test_entity_identity_and_shield_are_observable():
    battle = BattleState()
    knight_stats = battle.card_loader.get_card("Knight")
    prince_stats = battle.card_loader.get_card("DarkPrince")
    assert knight_stats is not None
    assert prince_stats is not None
    battle._spawn_troop(Position(7.0, 10.0), 0, knight_stats)
    battle._spawn_troop(Position(11.0, 10.0), 0, prince_stats)

    builder = CvObservationBuilder(card_vocab=["Knight", "DarkPrince"])
    obs = builder.build(battle, player_id=0)

    assert obs.board[15, 10, 7] == 0.5
    assert obs.board[15, 10, 11] == 1.0
    assert obs.board[17, 10, 7] == 0.0
    assert obs.board[17, 10, 11] == 1.0


def test_public_status_timers_and_special_movement_are_observable():
    battle = BattleState()
    knight_stats = battle.card_loader.get_card("Knight")
    prince_stats = battle.card_loader.get_card("Prince")
    assert knight_stats is not None and prince_stats is not None
    battle._spawn_troop(Position(7.0, 10.0), 0, knight_stats)
    own = battle.entities[max(battle.entities)]
    battle._spawn_troop(Position(11.0, 22.0), 1, prince_stats)
    enemy = battle.entities[max(battle.entities)]
    for entity in (own, enemy):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False

    own.stun_timer = 3.0
    own.slow_timer = 1.5
    enemy.haste_timer = 4.5
    enemy.is_charging = True

    builder = CvObservationBuilder(card_vocab=["Knight", "Prince"])
    obs = builder.build(battle, player_id=0)

    assert obs.board[23, 10, 7] == pytest.approx(0.5)
    assert obs.board[25, 10, 7] == pytest.approx(0.25)
    assert obs.board[28, 22, 11] == pytest.approx(0.75)
    assert obs.board[30, 22, 11] == 1.0
    assert float(obs.board[24].sum()) == 0.0
    assert float(obs.board[27].sum()) == 0.0


def test_visible_spell_payloads_preserve_card_identity():
    battle = BattleState()
    _prepare_hand(
        battle,
        0,
        ["Freeze", "Fireball", "Knight", "Archers", "Giant", "Minions", "Zap", "Cannon"],
    )
    assert battle.deploy_card(0, "Freeze", Position(9.0, 20.0))
    for _ in range(31):
        battle.step()

    builder = CvObservationBuilder(card_vocab=["Freeze", "Fireball"])
    obs = builder.build(battle, player_id=1)
    # Player-one canonical view rotates continuous point (9.0, 20.0) to
    # (9.0, 12.0) before rasterization.
    assert obs.board[14, 12, 9] > 0.0
    assert obs.board[16, 12, 9] == pytest.approx(0.5)


def test_nested_spawned_descendants_preserve_parent_card_identity():
    builder = CvObservationBuilder()

    assert builder._entity_name_to_value["Goblin"] == builder._entity_name_to_value[
        "GoblinBarrel"
    ]
    assert builder._entity_name_to_value[
        "DeliveryRecruit"
    ] == builder._entity_name_to_value["RoyalDelivery"]
    assert builder._entity_name_to_value[
        "RoyalDeliveryProjectile"
    ] == builder._entity_name_to_value["RoyalDelivery"]
    assert builder._entity_name_to_value["Golemite"] == builder._entity_name_to_value[
        "Golem"
    ]
    assert builder._entity_name_to_value["LavaPups"] == builder._entity_name_to_value[
        "LavaHound"
    ]
    assert builder._entity_name_to_value["Barbarian"] > 0.0


def test_champion_ability_status_is_visible_without_exposing_enemy_state():
    battle = BattleState()
    queen_stats = battle.card_loader.get_card("ArcherQueen")
    assert queen_stats is not None
    before = set(battle.entities)
    battle._spawn_troop(Position(9.0, 10.0), 0, queen_stats)
    queen = next(battle.entities[entity_id] for entity_id in set(battle.entities) - before)
    queen.deploy_delay_remaining = 0.0
    queen.placement_pending = False
    battle.players[0].elixir = 1.0
    assert battle.activate_champion_ability(0)

    builder = CvObservationBuilder(card_vocab=["ArcherQueen"])
    during_cast = builder.build(battle, player_id=0)
    assert during_cast.hud[10] > 0.99
    assert during_cast.hud[11] == 0.0

    for _ in range(4):
        battle.step()
    just_triggered = builder.build(battle, player_id=0)
    assert just_triggered.hud[10] > 0.9
    assert just_triggered.hud[11] > 0.99

    for _ in range(16):
        battle.step()
    active = builder.build(battle, player_id=0)
    assert active.hud[10] > 0.9
    assert active.hud[11] == pytest.approx(2.7 / 3.5, abs=1e-6)
