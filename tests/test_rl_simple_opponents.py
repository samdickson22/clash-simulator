from __future__ import annotations

import inspect

import pytest
import torch

from clasher.rl.simple_opponents import (
    SimpleNoopOpponentPolicy,
    SimpleTensorStrategyOpponentPolicy,
    SimpleUniformLegalOpponentPolicy,
)
from clasher.rl.simple_tensor_collector import SimpleTensorPolicyBoundary
from clasher.rl.strategy_bots import STRATEGY_NAMES
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_outputs import TensorPublicStructuredObservation
from clasher.torch_sim.simple_public_mask import SimplePublicMaskTypedTables


def _tables() -> SimplePublicMaskTypedTables:
    keys = (
        "<pad>",
        "<unknown>",
        "card_action:Knight",
        "card_action:Cannon",
        "card_action:Fireball",
    )
    return SimplePublicMaskTypedTables.compile(
        token_keys=keys,
        hand_playable=(False, False, True, True, True),
        elixir_cost=(0.0, 0.0, 3.0, 3.0, 4.0),
        is_spell=(False, False, False, False, True),
        non_rolling_spell=(False, False, False, False, True),
        is_building=(False, False, False, True, False),
        can_deploy_enemy_side=(False,) * 5,
        deploy_margin_tiles=(0,) * 5,
        deploy_radius_tiles=(0.5,) * 5,
        blocker_radius_tiles=(0.5,) * 5,
        ability_supported=(False,) * 5,
        ability_elixir_cost=(0.0,) * 5,
        blocked_tiles=(),
        authority="test-simple-opponent-tables",
    )


def _boundary(masks: torch.Tensor, decision_index: int) -> SimpleTensorPolicyBoundary:
    batch = masks.shape[0]
    entities = 4
    actor = TensorPublicStructuredObservation(
        entity_ids=torch.zeros((batch, 1, entities), dtype=torch.int64),
        entity_features=torch.zeros((batch, 1, entities, 20)),
        entity_mask=torch.zeros((batch, 1, entities), dtype=torch.bool),
        hand_ids=torch.tensor([[[2, 3, 4, 2, 3]]] * batch, dtype=torch.int64),
        global_features=torch.zeros((batch, 1, 20)),
    )
    actor.global_features[..., 5] = 0.8
    return SimpleTensorPolicyBoundary(
        actor=actor,
        critic=None,
        legal_mask=masks.clone(),
        public_action_masks=masks,
        previous_actions=torch.full((batch, 1), NO_OP_ACTION, dtype=torch.int64),
        previous_rewards=torch.zeros((batch, 1)),
        episode_starts=torch.zeros((batch, 1), dtype=torch.bool),
        recurrent_inputs=None,
        decision_index=decision_index,
    )


def _masks() -> torch.Tensor:
    masks = torch.zeros((3, 1, NO_OP_ACTION + 2), dtype=torch.bool)
    masks[..., NO_OP_ACTION] = True
    masks[0, 0, (0, 575, 576, 1_151)] = True
    masks[1, 0, (1_152, 1_727, 2_303)] = True
    masks[2, 0, (10, 700, 1_400, 2_200)] = True
    return masks


def test_noop_and_uniform_opponents_select_public_legal_actions() -> None:
    masks = _masks()
    boundary = _boundary(masks, 7)
    noop = SimpleNoopOpponentPolicy()(boundary).actions
    uniform = SimpleUniformLegalOpponentPolicy(seed=19)(boundary).actions

    assert noop.eq(NO_OP_ACTION).all()
    assert masks.gather(2, uniform[..., None]).all()
    assert torch.equal(
        uniform,
        SimpleUniformLegalOpponentPolicy(seed=19)(boundary).actions,
    )
    assert not torch.equal(
        uniform,
        SimpleUniformLegalOpponentPolicy(seed=19)(_boundary(masks, 8)).actions,
    )


@pytest.mark.parametrize("name", STRATEGY_NAMES)
def test_tensor_strategies_are_deterministic_public_mask_policies(name: str) -> None:
    masks = _masks()
    boundary = _boundary(masks, 0)
    policy = SimpleTensorStrategyOpponentPolicy(name, _tables(), device="cpu")

    first = policy(boundary).actions
    second = policy(boundary).actions

    assert torch.equal(first, second)
    assert masks.gather(2, first[..., None]).all()


def test_opponent_hot_paths_have_no_host_reads() -> None:
    source = "\n".join(
        (
            inspect.getsource(SimpleNoopOpponentPolicy.__call__),
            inspect.getsource(SimpleUniformLegalOpponentPolicy.__call__),
            inspect.getsource(SimpleTensorStrategyOpponentPolicy.__call__),
        )
    )
    for forbidden in (".item(", ".tolist(", ".cpu(", ".numpy("):
        assert forbidden not in source
