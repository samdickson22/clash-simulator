from __future__ import annotations

import numpy as np

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.location_lookahead import LocationLookahead


def test_candidate_actions_preserve_card_choice_and_rank_legal_tiles():
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    lookahead = LocationLookahead(action_space, top_k=3)
    slot = 2
    base_tile = 17
    mask = np.zeros(action_space.num_actions, dtype=np.bool_)
    for tile in (base_tile, 4, 9, 31):
        mask[slot * NUM_TILES + tile] = True
    logits = np.zeros((NUM_HAND_SLOTS, NUM_TILES), dtype=np.float32)
    logits[slot, 4] = 4.0
    logits[slot, 9] = 3.0
    logits[slot, base_tile] = 2.0
    logits[slot, 31] = 1.0

    actions = lookahead.candidate_actions(
        base_action=slot * NUM_TILES + base_tile,
        location_logits=logits,
        action_mask=mask,
    )

    assert actions == [
        slot * NUM_TILES + base_tile,
        slot * NUM_TILES + 4,
        slot * NUM_TILES + 9,
    ]
    assert {action // NUM_TILES for action in actions} == {slot}


def test_candidate_actions_do_not_override_noop_or_ability():
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    lookahead = LocationLookahead(action_space)
    mask = np.ones(action_space.num_actions, dtype=np.bool_)
    logits = np.zeros((NUM_HAND_SLOTS, NUM_TILES), dtype=np.float32)

    assert lookahead.candidate_actions(
        base_action=action_space.no_op_action,
        location_logits=logits,
        action_mask=mask,
    ) == [action_space.no_op_action]
    assert lookahead.candidate_actions(
        base_action=action_space.ability_action,
        location_logits=logits,
        action_mask=mask,
    ) == [action_space.ability_action]


def test_min_value_gain_must_be_non_negative():
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    with np.testing.assert_raises_regex(ValueError, "min_value_gain"):
        LocationLookahead(action_space, min_value_gain=-0.01)


def test_select_action_is_legal_and_does_not_mutate_live_battle():
    battle = BattleState(fast_path=True)
    battle.rng.seed(901)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    mask = action_space.legal_action_mask(battle, 0, fast_path=True)
    playable = np.flatnonzero(mask[: action_space.no_op_action])
    assert playable.size >= 2
    slot = int(playable[0]) // NUM_TILES
    same_slot = playable[playable // NUM_TILES == slot]
    assert same_slot.size >= 2
    base_action = int(same_slot[0])
    logits = np.zeros((NUM_HAND_SLOTS, NUM_TILES), dtype=np.float32)
    logits[slot, same_slot[0] % NUM_TILES] = 2.0
    logits[slot, same_slot[1] % NUM_TILES] = 3.0
    before = (
        battle.tick,
        battle.time,
        battle.rng.getstate(),
        tuple(
            (
                player.elixir,
                tuple(player.hand),
                tuple(player.deck),
                tuple(player.cycle_queue),
            )
            for player in battle.players
        ),
        tuple(
            (entity.id, entity.position.x, entity.position.y, entity.hitpoints)
            for entity in battle.entities.values()
        ),
    )

    result = LocationLookahead(
        action_space,
        top_k=2,
        horizon_ticks=4,
    ).select_action(
        battle,
        0,
        base_action=base_action,
        location_logits=logits,
        action_mask=mask,
    )

    after = (
        battle.tick,
        battle.time,
        battle.rng.getstate(),
        tuple(
            (
                player.elixir,
                tuple(player.hand),
                tuple(player.deck),
                tuple(player.cycle_queue),
            )
            for player in battle.players
        ),
        tuple(
            (entity.id, entity.position.x, entity.position.y, entity.hitpoints)
            for entity in battle.entities.values()
        ),
    )
    assert mask[result.action]
    assert result.action // NUM_TILES == slot
    assert before == after

    guarded = LocationLookahead(
        action_space,
        top_k=2,
        horizon_ticks=4,
        min_value_gain=2.0,
    ).select_action(
        battle,
        0,
        base_action=base_action,
        location_logits=logits,
        action_mask=mask,
    )
    assert guarded.action == base_action
