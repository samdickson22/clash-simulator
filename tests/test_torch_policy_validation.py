from __future__ import annotations

import random
from dataclasses import replace

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.policy_validation import (
    OUTSIDE_POLICY_TRANSITION_SCOPE,
    PROJECTED_GYM_TRANSITION_PROFILE,
    PUBLIC_ACTION_MASK_CONTRACT_V2,
    ProjectedGymTransition,
    compare_projected_gym_transitions,
    project_python_gym_transition,
    project_resident_gym_transition,
)
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_outputs import ResidentOutputProjector


def _paired_transitions(
    device: str,
) -> tuple[ProjectedGymTransition, ProjectedGymTransition]:
    battles = [
        BattleState(rng=random.Random(9_401)),
        BattleState(time=119.9, rng=random.Random(9_402)),
    ]
    builder = StructuredObservationBuilder(card_vocab=[], max_entities=16)
    engine = TensorResidentEngine.from_battles(
        battles,
        device=device,
        max_entities=16,
        max_objects=16,
    )
    projector = ResidentOutputProjector.from_engine(
        engine,
        battles,
        structured_builder=builder,
        max_entities=16,
    )
    action_masks = torch.ones((2, 2, 7), dtype=torch.bool)
    action_success = torch.tensor([[True, False], [True, True]])
    rewards = torch.tensor([[0.25, -0.25], [-1.0, 1.0]], dtype=torch.float64)
    done = torch.tensor([False, True])
    winner = torch.tensor([-1, 1], dtype=torch.int64)
    previous_actions = torch.tensor([[648, 649], [7, 8]], dtype=torch.int64)
    previous_rewards = torch.tensor([[0.0, -0.0], [0.5, -0.5]])
    episode_starts = torch.tensor([[True, True], [False, False]])
    recurrent = {
        "hidden": torch.arange(24, dtype=torch.float32).reshape(2, 2, 6),
        "public_play_event": torch.tensor([[0, 1], [2, 0]], dtype=torch.int64),
    }
    expected = project_python_gym_transition(
        battles,
        structured_builder=builder,
        action_success=action_success,
        rewards=rewards,
        done=done,
        winner=winner,
        previous_actions=previous_actions,
        previous_rewards=previous_rewards,
        episode_starts=episode_starts,
        public_action_masks=action_masks,
        public_action_mask_contract_version=PUBLIC_ACTION_MASK_CONTRACT_V2,
        include_privileged_critic=True,
        recurrent_inputs=recurrent,
    )
    actual = project_resident_gym_transition(
        projector,
        action_success=action_success.to(device),
        rewards=rewards.to(device),
        done=done.to(device),
        winner=winner.to(device),
        previous_actions=previous_actions.to(device),
        previous_rewards=previous_rewards.to(device),
        episode_starts=episode_starts.to(device),
        public_action_masks=action_masks.to(device),
        public_action_mask_contract_version=PUBLIC_ACTION_MASK_CONTRACT_V2,
        include_privileged_critic=True,
        recurrent_inputs={name: value.to(device) for name, value in recurrent.items()},
    )
    return expected, actual


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_existing_projectors_compare_complete_both_seat_transition(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    expected, actual = _paired_transitions(device)

    comparison = compare_projected_gym_transitions(expected, actual)

    comparison.require_passed()
    assert comparison.critic_compared
    assert comparison.public_action_mask_contract_version == 2
    assert comparison.recurrent_inputs_compared == (
        "hidden",
        "public_play_event",
    )
    assert comparison.outside_scope == OUTSIDE_POLICY_TRANSITION_SCOPE
    assert comparison.profile == PROJECTED_GYM_TRANSITION_PROFILE


def test_only_projected_actor_position_has_quarter_tile_tolerance() -> None:
    expected, actual = _paired_transitions("cpu")
    features = actual.actor.entity_features.clone()
    features[0, 0, 0, 0] += 0.25 / BOARD_WIDTH
    features[0, 1, 0, 1] += 0.25 / BOARD_HEIGHT
    at_limit = replace(
        actual,
        actor=replace(actual.actor, entity_features=features),
    )

    comparison = compare_projected_gym_transitions(expected, at_limit)

    comparison.require_passed()
    assert comparison.max_actor_position_error_tiles == pytest.approx(0.25)

    features = features.clone()
    features[0, 0, 0, 0] += 1e-4 / BOARD_WIDTH
    outside = replace(at_limit, actor=replace(at_limit.actor, entity_features=features))
    comparison = compare_projected_gym_transitions(expected, outside)
    assert not comparison.passed
    assert comparison.divergence is not None
    assert comparison.divergence.field == "actor.entity_features"
    assert "more than 0.25 tile" in comparison.divergence.reason


@pytest.mark.parametrize(
    ("field", "expected_path"),
    (
        ("identity", "actor.entity_ids"),
        ("hitpoints", "actor.entity_features"),
        ("status", "actor.entity_features"),
        ("readiness", "actor.global_features"),
        ("elixir", "actor.global_features"),
        ("mask", "public_action_masks"),
        ("action_success", "action_success"),
        ("reward", "rewards"),
        ("done", "done"),
        ("winner", "winner"),
        ("previous_action", "previous_actions"),
        ("previous_reward", "previous_rewards"),
        ("reset", "episode_starts"),
        ("recurrent", "recurrent_inputs.hidden"),
        ("critic", "critic.entity_features"),
    ),
)
def test_policy_material_fields_remain_exact(field: str, expected_path: str) -> None:
    expected, actual = _paired_transitions("cpu")
    if field == "identity":
        values = actual.actor.entity_ids.clone()
        values[0, 0, 0] += 1
        actual = replace(actual, actor=replace(actual.actor, entity_ids=values))
    elif field in {"hitpoints", "status"}:
        values = actual.actor.entity_features.clone()
        values[0, 0, 0, 9 if field == "hitpoints" else 14] += 1e-4
        actual = replace(actual, actor=replace(actual.actor, entity_features=values))
    elif field in {"readiness", "elixir"}:
        values = actual.actor.global_features.clone()
        values[0, 0, 14 if field == "readiness" else 5] += 1e-4
        actual = replace(actual, actor=replace(actual.actor, global_features=values))
    elif field == "mask":
        assert isinstance(actual.public_action_masks, torch.Tensor)
        values = actual.public_action_masks.clone()
        values[0, 0, 0] = ~values[0, 0, 0]
        actual = replace(actual, public_action_masks=values)
    elif field in {"action_success", "done", "reset"}:
        attribute = "episode_starts" if field == "reset" else field
        values = getattr(actual, attribute).clone()
        values.reshape(-1)[0] = ~values.reshape(-1)[0]
        actual = replace(actual, **{attribute: values})
    elif field in {"reward", "previous_reward"}:
        attribute = "rewards" if field == "reward" else "previous_rewards"
        values = getattr(actual, attribute).clone()
        values.reshape(-1)[0] += 1e-4
        actual = replace(actual, **{attribute: values})
    elif field in {"winner", "previous_action"}:
        attribute = "winner" if field == "winner" else "previous_actions"
        values = getattr(actual, attribute).clone()
        values.reshape(-1)[0] += 1
        actual = replace(actual, **{attribute: values})
    elif field == "recurrent":
        recurrent = dict(actual.recurrent_inputs or {})
        assert isinstance(recurrent["hidden"], torch.Tensor)
        recurrent["hidden"] = recurrent["hidden"].clone()
        recurrent["hidden"].reshape(-1)[0] += 1e-4
        actual = replace(actual, recurrent_inputs=recurrent)
    elif field == "critic":
        assert actual.critic is not None
        values = actual.critic.entity_features.clone()
        values[0, 0, 0, 0] += 1e-4
        actual = replace(
            actual,
            critic=replace(actual.critic, entity_features=values),
        )
    else:
        raise AssertionError(field)

    comparison = compare_projected_gym_transitions(expected, actual)
    assert not comparison.passed
    assert comparison.divergence is not None
    assert comparison.divergence.field == expected_path


def test_public_mask_v1_is_rejected_and_unprovided_masks_are_explicitly_unscoped() -> (
    None
):
    expected, _ = _paired_transitions("cpu")
    with pytest.raises(ValueError, match="contract v2 only"):
        replace(expected, public_action_mask_contract_version=1)

    without_mask = replace(
        expected,
        public_action_masks=None,
        public_action_mask_contract_version=None,
    )
    comparison = compare_projected_gym_transitions(without_mask, without_mask)
    comparison.require_passed()
    assert comparison.public_action_mask_contract_version is None
    assert "CPython RNG state and consumption" in comparison.outside_scope
