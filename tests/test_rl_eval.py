from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import torch

import clasher.rl.eval as eval_module
from clasher.rl.deck_pool import DeckPool
from clasher.rl.eval import LoadedPolicy


class _RejectingBuilder:
    def build(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("evaluation must obtain the actor view from the environment")


class _RecordingEnv:
    def __init__(self) -> None:
        self.battle = object()
        self.observation = object()
        self.mask = np.asarray([True, False, True], dtype=np.bool_)
        self.observation_calls: list[tuple[int, str]] = []
        self.mask_calls: list[tuple[int, str, object]] = []

    def get_structured_observation(
        self,
        player_id: int,
        *,
        actor_observation_domain: str,
    ) -> object:
        self.observation_calls.append((player_id, actor_observation_domain))
        return self.observation

    def get_action_mask(
        self,
        player_id: int,
        *,
        actor_observation_domain: str,
        structured_observation: object,
    ) -> np.ndarray:
        self.mask_calls.append(
            (player_id, actor_observation_domain, structured_observation)
        )
        return self.mask


class _RecordingModel:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            actor_observation_domain="causal-vision-v1",
            public_observation_confidence=True,
        )
        self.inputs: object | None = None

    def act(
        self,
        inputs: object,
        state: tuple[torch.Tensor, torch.Tensor],
        *,
        deterministic: bool,
    ) -> tuple[
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        tuple[torch.Tensor, torch.Tensor],
        object,
    ]:
        assert deterministic
        self.inputs = inputs
        scalar = torch.zeros((1, 1))
        return torch.ones((1, 1), dtype=torch.long), scalar, scalar, state, object()


def test_policy_step_uses_checkpoint_actor_domain_and_matching_mask(
    monkeypatch: Any,
) -> None:
    env = _RecordingEnv()
    model = _RecordingModel()
    loaded = LoadedPolicy(model=model, builder=_RejectingBuilder(), checkpoint={})  # type: ignore[arg-type]
    stacked = object()

    def fake_stack(
        observations: list[object],
        action_masks: np.ndarray,
        *_args: Any,
        **kwargs: Any,
    ) -> object:
        assert observations == [env.observation]
        np.testing.assert_array_equal(action_masks, env.mask[None, :])
        assert kwargs["public_observation_confidence"] is True
        return stacked

    monkeypatch.setattr(eval_module, "_stack_step_inputs", fake_stack)
    state = (torch.zeros((1, 1)), torch.zeros((1, 1)))

    action, returned_state, mask, _output = eval_module._policy_step(
        loaded,
        env,  # type: ignore[arg-type]
        1,
        state=state,
        previous_action=2,
        previous_reward=999.0,
        episode_start=False,
        deterministic=True,
        device=torch.device("cpu"),
    )

    assert action == 1
    assert returned_state is state
    np.testing.assert_array_equal(mask, env.mask)
    assert env.observation_calls == [(1, "causal-vision-v1")]
    assert env.mask_calls == [(1, "causal-vision-v1", env.observation)]
    assert model.inputs is stacked


def test_asymmetric_evaluation_binds_candidate_pool_to_both_seats(
    monkeypatch: Any,
) -> None:
    created: list[dict[str, Any]] = []

    class RecordingBattleEnv:
        def __init__(self, **kwargs: Any) -> None:
            created.append(kwargs)

    monkeypatch.setattr(eval_module, "SelfPlayBattleEnv", RecordingBattleEnv)
    candidate = SimpleNamespace(
        model=SimpleNamespace(
            config=SimpleNamespace(canonical_lane_globals=True)
        )
    )

    candidate_pool = SimpleNamespace(name="candidate")
    opponent_pool = SimpleNamespace(name="opponent")
    envs = eval_module._make_evaluation_envs(
        candidate=candidate,
        decks_path=SimpleNamespace(),
        sampling_decks_path=None,
        candidate_sampling_decks_path=candidate_pool,
        opponent_sampling_decks_path=opponent_pool,
        decision_interval=8,
        max_ticks=32,
        seed=1,
        mirror_match=False,
        reward_profile="objective-v1",
    )

    assert len(created) == 2
    assert set(envs) == {0, 1}
    assert created[0]["player0_sampling_decks_path"] is candidate_pool
    assert created[0]["player1_sampling_decks_path"] is opponent_pool
    assert created[0]["learner_player_id"] == 0
    assert created[1]["player0_sampling_decks_path"] is opponent_pool
    assert created[1]["player1_sampling_decks_path"] is candidate_pool
    assert created[1]["learner_player_id"] == 1


def test_asymmetric_evaluation_rejects_mirror_match() -> None:
    candidate = SimpleNamespace(
        model=SimpleNamespace(
            config=SimpleNamespace(canonical_lane_globals=True)
        )
    )
    try:
        eval_module._make_evaluation_envs(
            candidate=candidate,
            decks_path=SimpleNamespace(),
            sampling_decks_path=None,
            candidate_sampling_decks_path=SimpleNamespace(),
            opponent_sampling_decks_path=None,
            decision_interval=8,
            max_ticks=32,
            seed=1,
            mirror_match=True,
            reward_profile="objective-v1",
        )
    except ValueError as error:
        assert str(error) == (
            "asymmetric deck pools are incompatible with mirror_match"
        )
    else:
        raise AssertionError("mirror/asymmetric contract must fail closed")


def test_paired_asymmetric_decks_are_seat_invariant() -> None:
    candidate_pool = DeckPool(
        [[f"candidate_{deck}_{card}" for card in range(8)] for deck in range(3)],
        [1.0, 2.0, 3.0],
    )
    opponent_pool = DeckPool(
        [[f"opponent_{deck}_{card}" for card in range(8)] for deck in range(4)],
        [4.0, 3.0, 2.0, 1.0],
    )

    candidate_deck, opponent_deck = eval_module._sample_paired_ordered_decks(
        candidate_pool,
        opponent_pool,
        matchup_seed=1163101,
    )
    candidate_again, opponent_again = eval_module._sample_paired_ordered_decks(
        candidate_pool,
        opponent_pool,
        matchup_seed=1163101,
    )

    assert candidate_deck == candidate_again
    assert opponent_deck == opponent_again
    assert all(card.startswith("candidate_") for card in candidate_deck)
    assert all(card.startswith("opponent_") for card in opponent_deck)
    assert len(set(candidate_deck)) == 8
    assert len(set(opponent_deck)) == 8
