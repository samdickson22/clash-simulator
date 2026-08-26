from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace
from typing import Any

import pytest
import torch

from clasher.rl.deck_pool import load_deck_pool
from clasher.torch_sim.simple_cuda_graph import SimpleCudaGraphRunner
from clasher.torch_sim.simple_standard import (
    STANDARD_REGULATION_TICK,
    STANDARD_TIEBREAK_TICK,
)
from scripts.validate_simple_full_matches import (
    build_simple_runtime,
    select_actions,
    supported_simple_decks,
)


def test_cuda_graph_runner_rejects_cpu_runtime() -> None:
    runtime = SimpleNamespace(device=torch.device("cpu"), batch_size=1)
    actions = torch.zeros((1, 2), dtype=torch.int64)

    with pytest.raises(ValueError, match="requires a CUDA runtime"):
        SimpleCudaGraphRunner(runtime, actions)  # type: ignore[arg-type]


def _assert_tensor_fields_equal(left: Any, right: Any) -> None:
    for descriptor in fields(left):
        left_value = getattr(left, descriptor.name)
        if isinstance(left_value, torch.Tensor):
            assert torch.equal(left_value, getattr(right, descriptor.name))


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is unavailable")
def test_cuda_graph_runner_matches_eager_replays() -> None:
    decks = supported_simple_decks(
        [list(deck) for deck in load_deck_pool("decks.json")],
        device="cuda",
    )
    kwargs = {
        "seed": 202_608_264,
        "decks": decks,
        "batch_size": 2,
        "device": "cuda",
        "max_entities": 32,
        "max_effects": 32,
        "regulation_ticks": STANDARD_REGULATION_TICK,
        "tiebreak_ticks": STANDARD_TIEBREAK_TICK,
        "supported_only": True,
    }
    runtime = build_simple_runtime(**kwargs)
    reference = build_simple_runtime(**kwargs)
    observation = runtime.observe()
    reference_observation = reference.observe()
    example = select_actions(observation.legal_mask, "first-legal")
    runner = SimpleCudaGraphRunner(runtime, example)

    for _ in range(3):
        actions = select_actions(observation.legal_mask, "first-legal")
        reference_actions = select_actions(
            reference_observation.legal_mask, "first-legal"
        )
        assert torch.equal(actions, reference_actions)
        step = runner.step_tick(actions)
        reference_step = reference.step_tick(reference_actions)
        torch.cuda.synchronize(runtime.device)

        _assert_tensor_fields_equal(runtime.state, reference.state)
        _assert_tensor_fields_equal(runtime.action_state, reference.action_state)
        assert torch.equal(step.reward, reference_step.reward)
        assert torch.equal(step.done, reference_step.done)
        assert torch.equal(
            step.observation.actor.entity_ids,
            reference_step.observation.actor.entity_ids,
        )
        assert torch.equal(
            step.observation.actor.entity_features,
            reference_step.observation.actor.entity_features,
        )
        assert torch.equal(
            step.observation.legal_mask,
            reference_step.observation.legal_mask,
        )
        observation = step.observation
        reference_observation = reference_step.observation
