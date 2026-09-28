from __future__ import annotations

import numpy as np
import pytest

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.counterfactual_corpus import (
    ABILITY_KIND,
    INVALID_KIND,
    NO_OP_KIND,
    PLACEMENT_KIND,
    action_type_index,
    build_candidate_context,
    should_query_counterfactual,
    top_policy_candidates,
)
from clasher.rl.structured_obs import build_canonical_tile_features


def test_action_type_index_covers_canonical_action_space() -> None:
    no_op = NUM_HAND_SLOTS * NUM_TILES

    assert action_type_index(-1, no_op_action=no_op) == INVALID_KIND
    assert action_type_index(17, no_op_action=no_op) == 0
    assert action_type_index(NUM_TILES + 17, no_op_action=no_op) == 1
    assert action_type_index(no_op, no_op_action=no_op) == NUM_HAND_SLOTS
    assert action_type_index(no_op + 1, no_op_action=no_op) == NUM_HAND_SLOTS + 1
    with pytest.raises(ValueError, match="outside"):
        action_type_index(no_op + 2, no_op_action=no_op)


def test_query_schedule_spaces_playable_intervention_roots() -> None:
    kwargs = {
        "tick": 512,
        "last_query_decision": 0,
        "collected": 0,
        "states_per_game": 2,
        "minimum_tick": 256,
        "query_stride": 32,
        "can_play": True,
    }

    assert should_query_counterfactual(decision_index=32, **kwargs)
    assert not should_query_counterfactual(decision_index=31, **kwargs)
    assert not should_query_counterfactual(
        decision_index=32,
        **{**kwargs, "can_play": False},
    )
    assert should_query_counterfactual(
        decision_index=17,
        **{**kwargs, "last_query_decision": None},
    )
    assert should_query_counterfactual(
        decision_index=35,
        **{**kwargs, "last_query_decision": 3},
    )


def test_candidate_context_encodes_semantics_geometry_and_policy_mass() -> None:
    no_op = NUM_HAND_SLOTS * NUM_TILES
    ability = no_op + 1
    first = 7
    second = NUM_TILES + 19
    actions = np.asarray([no_op, first, second, ability, -1], dtype=np.int64)
    hand_ids = np.asarray([3, 4, 5, 6], dtype=np.int64)
    card_features = np.arange(8 * 16, dtype=np.float32).reshape(8, 16)
    tile_features = build_canonical_tile_features()
    logits = np.full(no_op + 2, -5.0, dtype=np.float32)
    mask = np.zeros(no_op + 2, dtype=np.bool_)
    mask[actions[:-1]] = True
    logits[first] = 2.0
    logits[second] = 1.0
    logits[no_op] = 0.0
    logits[ability] = -1.0

    context = build_candidate_context(
        candidate_actions=actions,
        hand_ids=hand_ids,
        card_stat_features=card_features,
        canonical_tile_features=tile_features,
        joint_logits=logits,
        action_mask=mask,
        no_op_action=no_op,
    )

    np.testing.assert_array_equal(context.valid, [True, True, True, True, False])
    np.testing.assert_array_equal(
        context.kinds,
        [NO_OP_KIND, PLACEMENT_KIND, PLACEMENT_KIND, ABILITY_KIND, INVALID_KIND],
    )
    np.testing.assert_array_equal(context.card_ids, [0, 3, 4, 0, 0])
    np.testing.assert_array_equal(context.card_features[1], card_features[3])
    np.testing.assert_array_equal(context.card_features[2], card_features[4])
    np.testing.assert_array_equal(context.tile_features[1], tile_features[first])
    np.testing.assert_array_equal(
        context.tile_features[2],
        tile_features[second % NUM_TILES],
    )
    np.testing.assert_array_equal(context.card_features[[0, 3, 4]], 0.0)
    np.testing.assert_array_equal(context.tile_features[[0, 3, 4]], 0.0)
    assert np.exp(context.policy_log_probabilities[:4]).sum() == pytest.approx(1.0)
    assert context.policy_type_log_probabilities[1] == pytest.approx(
        context.policy_log_probabilities[1]
    )
    assert np.isneginf(context.policy_logits[-1])


def test_candidate_context_rejects_illegal_candidate() -> None:
    no_op = NUM_HAND_SLOTS * NUM_TILES
    mask = np.zeros(no_op + 2, dtype=np.bool_)
    mask[no_op] = True
    with pytest.raises(ValueError, match="not legal"):
        build_candidate_context(
            candidate_actions=np.asarray([0]),
            hand_ids=np.asarray([1, 2, 3, 4]),
            card_stat_features=np.zeros((5, 16), dtype=np.float32),
            canonical_tile_features=build_canonical_tile_features(),
            joint_logits=np.zeros(no_op + 2, dtype=np.float32),
            action_mask=mask,
            no_op_action=no_op,
        )


def test_top_policy_candidates_cover_each_legal_type_before_truncation() -> None:
    no_op = NUM_HAND_SLOTS * NUM_TILES
    mask = np.zeros(no_op + 2, dtype=np.bool_)
    logits = np.full(no_op + 2, -10.0, dtype=np.float32)
    expected = [no_op]
    for slot, tile in enumerate((5, 6, 7, 8)):
        action = slot * NUM_TILES + tile
        mask[action] = True
        logits[action] = float(slot)
        expected.append(action)
    mask[no_op] = True
    logits[no_op] = 10.0

    candidates = top_policy_candidates(
        base_action=no_op,
        joint_logits=logits,
        action_mask=mask,
        no_op_action=no_op,
        max_candidates=5,
    )

    assert candidates[0] == no_op
    assert set(candidates.tolist()) == set(expected)
