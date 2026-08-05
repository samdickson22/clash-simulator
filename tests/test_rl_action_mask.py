from collections import deque
import copy

import numpy as np

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def _prepare_hand(battle: BattleState, player_id: int, cards: list[str], elixir: float = 10.0) -> None:
    player = battle.players[player_id]
    player.elixir = elixir
    player.hand = list(cards[:4])
    player.deck = list(cards[:8] if len(cards) >= 8 else cards + cards)
    player.cycle_queue = deque(player.deck[4:])


def test_mask_contains_noop_and_only_legal_actions():
    battle = BattleState()
    _prepare_hand(
        battle,
        0,
        ["Knight", "Archers", "Fireball", "Cannon", "Giant", "Minions", "Zap", "Musketeer"],
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)

    mask = action_space.legal_action_mask(battle, player_id=0)
    assert mask.shape == (action_space.num_actions,)
    assert mask.dtype == np.bool_
    assert mask[action_space.no_op_action]

    legal_actions = np.flatnonzero(mask)
    assert legal_actions.size > 1  # should include real deployment options

    # Sample a handful of legal actions and ensure apply_action succeeds.
    for action_id in legal_actions[:10]:
        if action_id == action_space.no_op_action:
            continue
        state = BattleState()
        _prepare_hand(
            state,
            0,
            ["Knight", "Archers", "Fireball", "Cannon", "Giant", "Minions", "Zap", "Musketeer"],
        )
        assert action_space.apply_action(state, 0, int(action_id))


def test_mask_blocks_actions_when_elixir_insufficient():
    battle = BattleState()
    _prepare_hand(
        battle,
        0,
        ["Golem", "ThreeMusketeers", "Pekka", "Rocket", "Knight", "Archers", "Zap", "Cannon"],
        elixir=0.0,
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    mask = action_space.legal_action_mask(battle, player_id=0)

    legal_actions = np.flatnonzero(mask)
    assert legal_actions.size == 1
    assert legal_actions[0] == action_space.no_op_action


def test_champion_ability_has_a_distinct_masked_action():
    battle = BattleState()
    queen_stats = battle.card_loader.get_card("ArcherQueen")
    assert queen_stats is not None
    battle._spawn_troop(Position(9.0, 10.0), 0, queen_stats)
    queen = max(
        (entity for entity in battle.entities.values() if entity.player_id == 0),
        key=lambda entity: entity.id,
    )
    queen.deploy_delay_remaining = 0.0
    queen.placement_pending = False
    queen.on_spawn()
    battle.players[0].elixir = 1.0
    action_space = DiscreteTileActionSpace()

    mask = action_space.legal_action_mask(battle, 0)
    assert mask[action_space.ability_action]
    assert action_space.apply_action(battle, 0, action_space.ability_action)
    assert not action_space.legal_action_mask(battle, 0)[action_space.ability_action]


def test_champion_ability_counts_as_an_available_elixir_spend():
    env = SelfPlayBattleEnv()
    env.reset(seed=1)
    assert env.battle is not None
    battle = env.battle
    queen_stats = battle.card_loader.get_card("ArcherQueen")
    assert queen_stats is not None
    battle._spawn_troop(Position(9.0, 10.0), 0, queen_stats)
    queen = max(
        (entity for entity in battle.entities.values() if entity.player_id == 0),
        key=lambda entity: entity.id,
    )
    queen.deploy_delay_remaining = 0.0
    queen.placement_pending = False
    queen.on_spawn()
    battle.players[0].elixir = 1.0
    # Make every card in hand unaffordable so the ability is the only legal spend.
    battle.players[0].hand = ["Golem", "ThreeMusketeers", "Pekka", "Rocket"]

    assert env._can_spend_elixir_now(0)


def test_champion_ability_is_masked_during_deployment():
    battle = BattleState()
    queen_stats = battle.card_loader.get_card("ArcherQueen")
    assert queen_stats is not None
    battle._spawn_troop(Position(9.0, 10.0), 0, queen_stats)
    battle.players[0].elixir = 10.0
    action_space = DiscreteTileActionSpace()

    assert not action_space.legal_action_mask(battle, 0)[action_space.ability_action]
    assert not action_space.apply_action(battle, 0, action_space.ability_action)
    assert battle.players[0].elixir == 10.0


def test_encode_decode_roundtrip_player_perspective():
    action_space = DiscreteTileActionSpace(canonical_perspective=True)

    action = action_space.encode_action(slot=2, world_x=3, world_y=25, player_id=1)
    decoded = action_space.decode_action(action, player_id=1)

    assert decoded.slot == 2
    assert decoded.position is not None
    assert int(decoded.position.x) == 3
    assert int(decoded.position.y) == 25


def test_decode_invalid_action_yields_noop():
    action_space = DiscreteTileActionSpace()
    decoded = action_space.decode_action(action_id=10_000_000, player_id=0)
    assert decoded.is_no_op
    assert decoded.slot is None
    assert decoded.position is None


def test_apply_action_rejects_out_of_range_ids_without_mutating_battle():
    battle = BattleState()
    action_space = DiscreteTileActionSpace()
    entity_ids = tuple(battle.entities)
    player_snapshots = [
        (
            player.elixir,
            tuple(player.hand),
            tuple(player.cycle_queue),
        )
        for player in battle.players
    ]

    for action_id in (-1, action_space.num_actions, 10_000_000):
        assert not action_space.apply_action(battle, 0, action_id)

    assert tuple(battle.entities) == entity_ids
    assert [
        (
            player.elixir,
            tuple(player.hand),
            tuple(player.cycle_queue),
        )
        for player in battle.players
    ] == player_snapshots


def test_selfplay_reports_out_of_range_action_as_failed():
    env = SelfPlayBattleEnv(decision_interval_ticks=0)
    env.reset(seed=17)

    _, _, info = env.step(
        {
            0: env.action_space.num_actions,
            1: env.action_space.no_op_action,
        }
    )

    assert info.action_success == {0: False, 1: True}


def test_fast_mask_matches_legacy_mask_on_same_state():
    battle = BattleState()
    _prepare_hand(
        battle,
        0,
        ["Knight", "Archers", "Fireball", "Cannon", "Giant", "Minions", "Zap", "Musketeer"],
    )
    _prepare_hand(
        battle,
        1,
        ["HogRider", "IceGolem", "Log", "Tesla", "Knight", "Arrows", "Fireball", "Musketeer"],
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)

    legacy0 = action_space.legal_action_mask(battle, player_id=0, fast_path=False)
    legacy1 = action_space.legal_action_mask(battle, player_id=1, fast_path=False)

    fast_battle = copy.deepcopy(battle)
    fast_battle.fast_path = True
    fast_battle._refresh_fast_path_caches()
    fast0 = action_space.legal_action_mask(fast_battle, player_id=0, fast_path=True)
    fast1 = action_space.legal_action_mask(fast_battle, player_id=1, fast_path=True)

    assert np.array_equal(legacy0, fast0)
    assert np.array_equal(legacy1, fast1)


def test_every_enabled_card_mask_matches_both_engines_and_canonical_sides():
    battle = BattleState(fast_path=True)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    cards = unique_cards_from_decks(load_deck_pool())

    for card_name in cards:
        for player_id in (0, 1):
            _prepare_hand(battle, player_id, [card_name] * 8)
        battle._refresh_fast_path_caches()

        masks = {}
        for player_id in (0, 1):
            legacy = action_space.legal_action_mask(
                battle,
                player_id,
                fast_path=False,
            )
            fast = action_space.legal_action_mask(
                battle,
                player_id,
                fast_path=True,
            )
            np.testing.assert_array_equal(legacy, fast)
            masks[player_id] = legacy

        np.testing.assert_array_equal(masks[0], masks[1])


def test_fast_mask_sees_building_spawned_earlier_in_same_decision_window():
    battle = BattleState(fast_path=True)
    red_left = next(
        entity
        for entity in battle.entities.values()
        if (
            entity.player_id == 1
            and getattr(entity, "_crown_tower_slot", None) == "left"
        )
    )
    red_left.take_damage(red_left.hitpoints)
    battle._update_tower_hp()
    _prepare_hand(battle, 0, ["Cannon"] * 8)
    _prepare_hand(battle, 1, ["Cannon"] * 8)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    position = Position(6.5, 18.5)

    assert battle.deploy_card(0, "Cannon", position)
    second_action = action_space.encode_action(0, 6, 18, 1)
    mask = action_space.legal_action_mask(
        battle,
        player_id=1,
        fast_path=True,
    )

    assert not mask[second_action]


def test_timed_death_payload_blocks_troop_and_building_actions_in_both_masks():
    battle = BattleState()
    _prepare_hand(
        battle,
        0,
        ["Knight", "Cannon", "Fireball", "Archers"],
    )
    balloon_stats = battle.card_loader.get_card("Balloon")
    assert balloon_stats is not None
    battle._spawn_troop(Position(9.5, 10.5), 1, balloon_stats)
    balloon = max(
        (entity for entity in battle.entities.values() if entity.player_id == 1),
        key=lambda entity: entity.id,
    )
    balloon.deploy_delay_remaining = 0.0
    balloon.placement_pending = False
    balloon.take_damage(balloon.hitpoints)

    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    troop_action = action_space.encode_action(0, 9, 10, 0)
    building_action = action_space.encode_action(1, 9, 10, 0)
    legacy = action_space.legal_action_mask(battle, 0, fast_path=False)

    fast_battle = copy.deepcopy(battle)
    fast_battle.fast_path = True
    fast_battle._refresh_fast_path_caches()
    fast = action_space.legal_action_mask(fast_battle, 0, fast_path=True)

    assert np.array_equal(legacy, fast)
    assert not legacy[troop_action]
    assert not legacy[building_action]
    assert not battle.deploy_card(0, "Knight", Position(9.5, 10.5))
    assert not battle.deploy_card(0, "Cannon", Position(9.5, 10.5))


def test_fast_miner_mask_matches_full_arena_rule_for_both_players():
    action_space = DiscreteTileActionSpace(canonical_perspective=True)

    for player_id, enemy_y in ((0, 20), (1, 10)):
        battle = BattleState(fast_path=True)
        _prepare_hand(
            battle,
            player_id,
            ["Miner", "Knight", "Fireball", "Cannon"],
        )
        battle._refresh_fast_path_caches()

        legacy = action_space.legal_action_mask(
            battle,
            player_id=player_id,
            fast_path=False,
        )
        fast = action_space.legal_action_mask(
            battle,
            player_id=player_id,
            fast_path=True,
        )

        assert np.array_equal(legacy, fast)
        enemy_side_action = action_space.encode_action(
            slot=0,
            world_x=9,
            world_y=enemy_y,
            player_id=player_id,
        )
        assert legacy[enemy_side_action]
        assert fast[enemy_side_action]


def test_wide_formation_margin_matches_in_both_action_masks():
    action_space = DiscreteTileActionSpace(canonical_perspective=True)

    for player_id, friendly_y in ((0, 10), (1, 21)):
        battle = BattleState(fast_path=True)
        _prepare_hand(
            battle,
            player_id,
            ["RoyalHogs", "Knight", "Fireball", "Cannon"],
        )
        battle._refresh_fast_path_caches()
        legacy = action_space.legal_action_mask(
            battle,
            player_id=player_id,
            fast_path=False,
        )
        fast = action_space.legal_action_mask(
            battle,
            player_id=player_id,
            fast_path=True,
        )

        assert np.array_equal(legacy, fast)
        for world_x in (1, 16):
            action = action_space.encode_action(
                slot=0,
                world_x=world_x,
                world_y=friendly_y,
                player_id=player_id,
            )
            assert not legacy[action]
        for world_x in (2, 15):
            action = action_space.encode_action(
                slot=0,
                world_x=world_x,
                world_y=friendly_y,
                player_id=player_id,
            )
            assert legacy[action]


def test_projectile_spawn_spells_can_target_water_like_other_arena_wide_spells():
    battle = BattleState()
    _prepare_hand(
        battle,
        0,
        ["GoblinBarrel", "Fireball", "Knight", "Cannon"],
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    water = action_space.encode_action(0, 9, 16, 0)
    bridge = action_space.encode_action(0, 3, 16, 0)
    fireball_water = action_space.encode_action(1, 9, 16, 0)

    legacy = action_space.legal_action_mask(battle, 0, fast_path=False)
    fast_battle = copy.deepcopy(battle)
    fast_battle.fast_path = True
    fast_battle._refresh_fast_path_caches()
    fast = action_space.legal_action_mask(fast_battle, 0, fast_path=True)

    assert np.array_equal(legacy, fast)
    assert legacy[water]
    assert legacy[bridge]
    assert legacy[fireball_water]
    assert battle.deploy_card(0, "GoblinBarrel", Position(9.5, 16.5))
