from __future__ import annotations

from dataclasses import fields, replace

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.rl.simple_counterfactual import SimpleTerminalCounterfactualEvaluator
from clasher.rl.simple_tensor_collector import (
    SimplePublicActionMaskV2,
    SimpleTensorMaskRequest,
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
)
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_outcomes import FastMatchRules
from clasher.torch_sim.simple_reward_v2 import SimpleRewardV2Config
from clasher.torch_sim.simple_rollout import SimpleGymRolloutBridge
from clasher.torch_sim.simple_standard import compile_standard_simple_setup


class _ExactMaskProvider:
    def __call__(self, request: SimpleTensorMaskRequest) -> SimplePublicActionMaskV2:
        return SimplePublicActionMaskV2(
            masks=request.observation.legal_mask,
            semantics_id="test-public-mask-v2",
            semantics={
                "schema_version": 1,
                "source": "test-exact-actor-boundary",
            },
        )


class _NoopRecurrentPolicy:
    def __call__(
        self, boundary: SimpleTensorPolicyBoundary
    ) -> SimpleTensorPolicyDecision:
        recurrent = (
            None
            if boundary.recurrent_inputs is None
            else {
                name: value + 1.0 for name, value in boundary.recurrent_inputs.items()
            }
        )
        return SimpleTensorPolicyDecision(
            actions=torch.full(
                boundary.previous_actions.shape,
                NO_OP_ACTION,
                dtype=torch.int64,
                device=boundary.previous_actions.device,
            ),
            next_recurrent_inputs=recurrent,
        )


def _runtimes(
    device_name: str,
    *,
    source_batch: int = 1,
    candidate_count: int = 6,
) -> tuple[SimpleGymRolloutBridge, SimpleGymRolloutBridge]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    if device_name == "mps" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ("Knight",),
        device=device_name,
        canonical_lane_globals=True,
    )
    setup = replace(setup, rules=FastMatchRules(regulation_ticks=8, tiebreak_ticks=12))
    cards = setup.spawn_blueprints.fast_cards
    knight = setup.cards.name_to_id["Knight"]
    entity = torch.zeros((2, cards.size), dtype=torch.int64, device=setup.device)
    entity[:, knight] = torch.tensor((101, 201), device=setup.device)
    hand = torch.zeros(cards.size, dtype=torch.int64, device=setup.device)
    hand[knight] = 301

    def runtime(batch_size: int) -> SimpleGymRolloutBridge:
        decks = [[["Knight"] * 8, ["Knight"] * 8] for _ in range(batch_size)]
        result = setup.create_runtime(
            decks,
            entity_token_lookup=entity,
            hand_token_lookup=hand,
            canonical_lane_globals=True,
            max_entities=24,
            max_effects=16,
            include_privileged_critic=True,
        )
        return SimpleGymRolloutBridge(
            result,
            decision_interval=4,
            reward_v2_config=SimpleRewardV2Config(gamma=0.99),
            strict_reset_check=False,
        )

    return runtime(source_batch), runtime(source_batch * candidate_count)


@pytest.mark.parametrize("device_name", ("cpu", "cuda", "mps"))
def test_six_way_counterfactual_fork_preserves_public_root_and_terminal_metrics(
    device_name: str,
) -> None:
    source, scratch = _runtimes(device_name)
    source.runtime.state.hp[0, 3] = 0.0
    source_root = source.observe()
    source_tick = source.runtime.state.tick.clone()
    source_hp = source.runtime.state.hp.clone()
    source_history = source.adapter.history

    player_legal = source_root.legal_mask[0, 0]
    non_noop = torch.where(
        player_legal
        & (
            torch.arange(
                player_legal.shape[0],
                dtype=torch.int64,
                device=player_legal.device,
            )
            != NO_OP_ACTION
        )
    )[0][:5]
    assert non_noop.shape == (5,)
    candidates = torch.full(
        (1, 6, 2),
        NO_OP_ACTION,
        dtype=torch.int64,
        device=source.device,
    )
    candidates[0, 1:, 0] = non_noop
    recurrent = {
        "hidden": torch.zeros((1, 2, 3), device=source.device),
        "cell": torch.ones((1, 2, 3), device=source.device),
    }
    evaluator = SimpleTerminalCounterfactualEvaluator(
        scratch,
        public_mask_provider=_ExactMaskProvider(),
        policy=_NoopRecurrentPolicy(),
        terminal_check_interval=1,
    )

    result = evaluator.evaluate(
        source,
        candidates,
        learner_players=torch.zeros(1, dtype=torch.int64, device=source.device),
        recurrent_inputs=recurrent,
        max_decisions=4,
    )

    assert result.flat_candidates == 6
    assert result.source_rows.tolist() == [0] * 6
    assert result.candidate_index.tolist() == list(range(6))
    assert torch.equal(result.first_actions, candidates.reshape(6, 2))
    assert result.first_action_success.all()
    for descriptor in fields(result.root_actor):
        actual = getattr(result.root_actor, descriptor.name)
        expected = getattr(source_root.actor, descriptor.name).expand(
            6, *getattr(source_root.actor, descriptor.name).shape[1:]
        )
        assert torch.equal(actual, expected), descriptor.name
    assert torch.equal(
        result.root_legal_masks,
        source_root.legal_mask.expand(6, *source_root.legal_mask.shape[1:]),
    )
    assert result.terminal_winner.eq(0).all()
    assert result.terminal_value.eq(1.0).all()
    assert result.terminal_crowns[:, 0].eq(1).all()
    assert result.terminal_crowns[:, 1].eq(0).all()
    assert result.terminal_tower_hp[:, 1, 0].eq(0.0).all()
    assert result.terminal_tower_damage_received[:, 0].eq(0.0).all()
    assert result.terminal_tower_damage_received[:, 1].gt(0.0).all()
    assert result.decision_count.eq(2).all()
    assert result.native_ticks.eq(8).all()
    assert result.committed.all()
    assert not result.fallback_rows.any()
    assert result.all_rows_admitted.all()
    assert result.recurrent_inputs is not None
    assert result.recurrent_inputs["hidden"].eq(2.0).all()
    assert result.recurrent_inputs["cell"].eq(3.0).all()

    assert torch.equal(source.runtime.state.tick, source_tick)
    assert torch.equal(source.runtime.state.hp, source_hp)
    assert source.adapter.history is source_history


def test_counterfactual_continuation_freezes_early_terminal_rows() -> None:
    source, scratch = _runtimes("cpu", source_batch=2)
    source.runtime.state.hp[0, 3] = 0.0
    candidates = torch.full(
        (2, 6, 2),
        NO_OP_ACTION,
        dtype=torch.int64,
        device=source.device,
    )
    evaluator = SimpleTerminalCounterfactualEvaluator(
        scratch,
        public_mask_provider=_ExactMaskProvider(),
        policy=_NoopRecurrentPolicy(),
        terminal_check_interval=0,
    )

    result = evaluator.evaluate(
        source,
        candidates,
        learner_players=torch.zeros(2, dtype=torch.int64),
        recurrent_inputs={
            "hidden": torch.zeros((2, 2, 1)),
            "cell": torch.zeros((2, 2, 1)),
        },
        max_decisions=3,
    )

    first = result.source_rows == 0
    second = result.source_rows == 1
    assert result.terminal_winner[first].eq(0).all()
    assert result.terminal_value[first].eq(1.0).all()
    assert result.decision_count[first].eq(2).all()
    assert result.native_ticks[first].eq(8).all()
    assert result.terminal_winner[second].lt(0).all()
    assert result.terminal_value[second].eq(0.0).all()
    assert result.decision_count[second].eq(3).all()
    assert result.native_ticks[second].eq(12).all()
    assert result.committed.all()
    assert result.all_rows_admitted.all()
    assert not result.fallback_rows.any()
    assert result.recurrent_inputs is not None
    assert result.recurrent_inputs["hidden"][first].eq(2.0).all()
    assert result.recurrent_inputs["hidden"][second].eq(3.0).all()
