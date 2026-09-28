from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.counterfactual_corpus import top_policy_candidates
from clasher.rl.model import PolicyOutput
from clasher.rl.oracle_planner import FixedDepthThompsonOracle
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.value_guided_search import (
    CandidateValue,
    RecurrentValueGuidedSearch,
    clone_search_env,
)


def test_search_environment_clone_replays_exact_step_without_mutating_source() -> None:
    source = SelfPlayBattleEnv(
        seed=2301,
        decision_interval_ticks=2,
        max_ticks=64,
        engine_fast_path="on",
    )
    source.reset(seed=2301)
    assert source.battle is not None
    first = clone_search_env(source)
    second = clone_search_env(source)
    actions = {
        0: source.action_space.no_op_action,
        1: source.action_space.no_op_action,
    }
    source_key = FixedDepthThompsonOracle()._state_key(source.battle)

    rewards_first, done_first, info_first = first.step(actions)
    rewards_second, done_second, info_second = second.step(actions)

    assert source.battle.tick == 0
    assert FixedDepthThompsonOracle()._state_key(source.battle) == source_key
    assert first.battle is not None and second.battle is not None
    assert FixedDepthThompsonOracle()._state_key(
        first.battle
    ) == FixedDepthThompsonOracle()._state_key(second.battle)
    assert rewards_first == rewards_second
    assert done_first == done_second
    assert info_first == info_second


def test_search_candidates_cover_distinct_legal_action_types() -> None:
    num_actions = NUM_HAND_SLOTS * NUM_TILES + 2
    search = object.__new__(RecurrentValueGuidedSearch)
    search.max_candidates = 6
    search.locations_per_slot = 1
    search.spatially_diverse_locations = False
    search.policy = SimpleNamespace(model=SimpleNamespace(num_actions=num_actions))
    mask = np.zeros(num_actions, dtype=np.bool_)
    logits = torch.full((1, 1, num_actions), -100.0)
    expected = []
    for slot, tile in ((0, 9), (1, 7), (3, 12)):
        action = slot * NUM_TILES + tile
        mask[action] = True
        logits[0, 0, action] = float(slot + 1)
        expected.append(action)
    mask[-2:] = True
    logits[0, 0, -2] = 8.0
    logits[0, 0, -1] = 7.0
    output = PolicyOutput(
        joint_logits=logits,
        values=torch.zeros((1, 1)),
        opponent_hand_logits=torch.zeros((1, 1, 1)),
        opponent_elixir=torch.zeros((1, 1)),
        next_state=(torch.zeros((1, 1)), torch.zeros((1, 1))),
        action_type_logits=torch.zeros((1, 1, NUM_HAND_SLOTS + 2)),
        location_logits=torch.zeros((1, 1, NUM_HAND_SLOTS, NUM_TILES)),
    )

    candidates = search.candidate_actions(
        base_action=expected[0],
        output=output,
        action_mask=mask,
    )

    assert candidates[0] == expected[0]
    assert set(candidates) == {*expected, num_actions - 2, num_actions - 1}
    action_types = {
        action // NUM_TILES if action < NUM_HAND_SLOTS * NUM_TILES else action
        for action in candidates
    }
    assert len(action_types) == len(candidates)


def test_search_candidates_cover_types_before_alternate_locations() -> None:
    num_actions = NUM_HAND_SLOTS * NUM_TILES + 2
    search = object.__new__(RecurrentValueGuidedSearch)
    search.max_candidates = 7
    search.locations_per_slot = 3
    search.spatially_diverse_locations = False
    search.policy = SimpleNamespace(model=SimpleNamespace(num_actions=num_actions))
    mask = np.zeros(num_actions, dtype=np.bool_)
    logits = torch.full((1, 1, num_actions), -100.0)
    primaries = []
    for slot in range(NUM_HAND_SLOTS):
        for rank, tile in enumerate((9, 7, 12)):
            action = slot * NUM_TILES + tile
            mask[action] = True
            logits[0, 0, action] = 100.0 - rank - slot * 10.0
            if rank == 0:
                primaries.append(action)
    mask[-2] = True
    logits[0, 0, -2] = -50.0
    output = PolicyOutput(
        joint_logits=logits,
        values=torch.zeros((1, 1)),
        opponent_hand_logits=torch.zeros((1, 1, 1)),
        opponent_elixir=torch.zeros((1, 1)),
        next_state=(torch.zeros((1, 1)), torch.zeros((1, 1))),
        action_type_logits=torch.zeros((1, 1, NUM_HAND_SLOTS + 2)),
        location_logits=torch.zeros((1, 1, NUM_HAND_SLOTS, NUM_TILES)),
    )

    candidates = search.candidate_actions(
        base_action=primaries[0],
        output=output,
        action_mask=mask,
    )

    assert candidates[0] == primaries[0]
    assert set(primaries).issubset(candidates)
    assert num_actions - 2 in candidates
    assert len(candidates) == 7


def test_spatially_diverse_locations_escape_adjacent_logit_cluster() -> None:
    search = object.__new__(RecurrentValueGuidedSearch)
    search.locations_per_slot = 3
    search.spatially_diverse_locations = True
    legal = np.asarray([0, 1, 2, NUM_TILES - 2, NUM_TILES - 1], dtype=np.int64)
    logits = np.full(NUM_TILES, -100.0)
    logits[0] = 10.0
    logits[1] = 9.0
    logits[2] = 8.0
    logits[NUM_TILES - 2] = 0.0
    logits[NUM_TILES - 1] = -1.0

    selected = search._ordered_slot_tiles(legal, logits)

    assert selected[0] == 0
    assert selected[1] == NUM_TILES - 1
    assert len(selected) == 3


def test_search_risk_gate_preserves_favorable_base_action() -> None:
    search = object.__new__(RecurrentValueGuidedSearch)
    search.minimum_value_gain = 0.02
    search.maximum_override_base_probability = 0.65

    selected = search._choose_candidate(
        [
            CandidateValue(action=10, probability=0.70),
            CandidateValue(action=11, probability=0.90),
        ]
    )

    assert selected.action == 10


def test_search_risk_gate_allows_large_recovery_when_base_is_unfavorable() -> None:
    search = object.__new__(RecurrentValueGuidedSearch)
    search.minimum_value_gain = 0.02
    search.maximum_override_base_probability = 0.65

    selected = search._choose_candidate(
        [
            CandidateValue(action=10, probability=0.49),
            CandidateValue(action=11, probability=0.70),
        ]
    )

    assert selected.action == 11


def test_runtime_action_value_candidates_match_collection_search_defaults() -> None:
    num_actions = NUM_HAND_SLOTS * NUM_TILES + 2
    search = object.__new__(RecurrentValueGuidedSearch)
    search.max_candidates = 6
    search.locations_per_slot = 1
    search.spatially_diverse_locations = False
    search.policy = SimpleNamespace(model=SimpleNamespace(num_actions=num_actions))
    rng = np.random.default_rng(2301)
    mask = rng.random(num_actions) < 0.15
    mask[-2] = True
    logits_array = rng.normal(size=num_actions).astype(np.float32)
    logits = torch.from_numpy(logits_array).reshape(1, 1, -1)
    output = PolicyOutput(
        joint_logits=logits,
        values=torch.zeros((1, 1)),
        opponent_hand_logits=torch.zeros((1, 1, 1)),
        opponent_elixir=torch.zeros((1, 1)),
        next_state=(torch.zeros((1, 1)), torch.zeros((1, 1))),
        action_type_logits=torch.zeros((1, 1, NUM_HAND_SLOTS + 2)),
        location_logits=torch.zeros((1, 1, NUM_HAND_SLOTS, NUM_TILES)),
    )

    expected = search.candidate_actions(
        base_action=num_actions - 2,
        output=output,
        action_mask=mask,
    )
    actual = top_policy_candidates(
        base_action=num_actions - 2,
        joint_logits=logits_array,
        action_mask=mask,
        no_op_action=num_actions - 2,
        max_candidates=6,
    )

    assert actual.tolist() == list(expected)
