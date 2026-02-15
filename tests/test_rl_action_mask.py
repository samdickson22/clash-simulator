from collections import deque
import copy

import numpy as np

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace


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
