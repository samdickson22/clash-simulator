from __future__ import annotations

import inspect
from argparse import Namespace
from dataclasses import fields, replace
from typing import Any

import pytest
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.simple_pytorch_backend import (
    SIMPLE_PYTORCH_BACKEND,
    SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH,
    SIMPLE_PYTORCH_EXECUTION_EAGER,
    SimplePytorchBackendError,
    SimplePytorchTrainingCollector,
    load_current_client_typed_vocabulary,
    load_simple_supported_decks,
)
from clasher.rl.simple_tensor_collector import SimpleTensorMaskRequest
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import RolloutBatch, _validate_simple_pytorch_args
from clasher.torch_sim.actions import ABILITY_ACTION, NO_OP_ACTION
from clasher.torch_sim.simple_cuda_graph import SimpleCudaGraphRunner
from clasher.torch_sim.simple_public_mask import (
    SIMPLE_PUBLIC_MASK_SEMANTICS_ID,
    SimpleCollectorPublicMaskV2Provider,
    SimplePublicMaskV2Provider,
)


def _simple_args(**overrides: object) -> Namespace:
    values: dict[str, object] = {
        "simulation_backend": SIMPLE_PYTORCH_BACKEND,
        "actor_workers": 1,
        "resume_latest": False,
        "resume_from": None,
        "opponent_mode": "selfplay",
        "actor_observation_domain": "simulator-exact",
        "reward_profile": "objective-v1",
        "reward_shaping_gamma": None,
        "elixir_leak_penalty_scale": 0.0,
        "engine_fast_path": "off",
        "max_ticks": 6_000,
        "sampling_decks_path": None,
        "learner_sampling_decks_path": None,
        "opponent_sampling_decks_path": None,
        "matchups_path": None,
        "defense_scenario_probability": 0.0,
    }
    values.update(overrides)
    return Namespace(**values)


def test_simple_backend_contract_and_typed_variants_fail_closed() -> None:
    vocabulary = load_current_client_typed_vocabulary()
    artifact = load_simple_supported_decks()

    assert len(vocabulary.token_names) == 494
    assert len(artifact.public_cards) == 66
    assert vocabulary.resolve("Archers", "card_action") == vocabulary.resolve(
        "Archer", "card_action"
    )
    base = vocabulary.resolve("Knight", "card_action")
    hero = vocabulary.resolve("Knight_hero", "card_action")
    evolution = vocabulary.resolve("Knight_EV1", "card_action")
    assert base > 1 and hero > 1 and evolution > 1
    assert len({base, hero, evolution}) == 3
    assert vocabulary.resolve("Unknown_hero", "card_action") == 0
    _validate_simple_pytorch_args(_simple_args())


def _training_collector(
    device_name: str = "cpu",
    *,
    batch_size: int = 1,
    execution_mode: str | None = None,
) -> SimplePytorchTrainingCollector:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    torch.manual_seed(7)
    vocabulary = load_current_client_typed_vocabulary()
    builder = StructuredObservationBuilder(
        decks_path="decks.json",
        token_names=vocabulary.token_names,
        max_entities=128,
        canonical_lane_globals=True,
    )
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.spec.max_entities,
        canonical_lane_globals=True,
        d_model=32,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=32,
        dropout=0.0,
    )
    model = ClasherPolicy(config, builder.card_stat_features).to(device)
    return SimplePytorchTrainingCollector(
        model=model,
        builder=builder,
        batch_size=batch_size,
        device=device,
        decision_interval=2,
        gamma=0.995,
        supported_decks_path="training_decks/simple_gym_supported_v1.json",
        typed_vocabulary_path=(
            "reports/current_client_youtube_stable_vocabulary_v1.json"
        ),
        mirror_match=False,
        _execution_mode_override=execution_mode,
    )


def test_one_decision_collects_existing_ppo_rollout_shape() -> None:
    collector = _training_collector()
    model = collector.policy.model
    arrays, next_state, previous_actions, previous_rewards, episode_starts = (
        collector.collect(1, model.initial_state(2, device="cpu"))
    )
    rollout = RolloutBatch(**arrays)

    assert rollout.actions.shape == (2, 1)
    assert rollout.action_masks.shape == (2, 1, model.num_actions)
    assert rollout.entity_ids.shape == (2, 1, 128)
    assert rollout.transitions == 2
    assert rollout.action_masks[torch.arange(2).numpy(), 0, rollout.actions[:, 0]].all()
    assert next_state[0].shape == (2, 32)
    assert (
        previous_actions.shape == previous_rewards.shape == episode_starts.shape == (2,)
    )
    metadata = collector.checkpoint_metadata()
    assert metadata["public_action_mask_contract_version"] == 2
    assert metadata["public_action_mask_semantics_id"] == (
        SIMPLE_PUBLIC_MASK_SEMANTICS_ID
    )
    assert metadata["public_action_mask_semantics"]["ability_policy"] == (
        "actor-visible-supported-champion-v1"
    )
    assert metadata["reward_contract_id"] == "objective-v1-gamma-v1"
    assert metadata["execution_mode"] == SIMPLE_PYTORCH_EXECUTION_EAGER
    assert metadata["fresh_only"] is True


def test_execution_mode_metadata_fails_closed() -> None:
    collector = _training_collector()
    collector.metadata = replace(
        collector.metadata,
        execution_mode=SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH,
    )

    with pytest.raises(SimplePytorchBackendError, match="does not match"):
        collector.checkpoint_metadata()

    with pytest.raises(SimplePytorchBackendError, match="unsupported"):
        _training_collector(execution_mode="automatic-fallback")

    with pytest.raises(SimplePytorchBackendError, match="requires a CUDA"):
        _training_collector(execution_mode=SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_route_uses_committed_actor_v2_mask_authority(device_name: str) -> None:
    collector = _training_collector(device_name)
    bridge = collector.collector.bridge
    adapter = collector.collector.public_mask_provider
    assert isinstance(adapter, SimpleCollectorPublicMaskV2Provider)
    assert isinstance(adapter.provider, SimplePublicMaskV2Provider)
    assert adapter.provider.tables is collector.public_mask_tables
    assert collector.public_mask_tables.semantics_id == (
        SIMPLE_PUBLIC_MASK_SEMANTICS_ID
    )
    expected_mode = (
        SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH
        if device_name == "cuda"
        else SIMPLE_PYTORCH_EXECUTION_EAGER
    )
    assert collector.metadata.execution_mode == expected_mode
    assert isinstance(bridge.runtime, SimpleCudaGraphRunner) == (
        expected_mode == SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH
    )

    for decision_index in range(4):
        observation = bridge.observe()
        request = SimpleTensorMaskRequest(observation, decision_index, False)
        actual = adapter(request).masks
        placements = actual[..., : 4 * 18 * 32]
        first = placements.to(torch.int64).argmax(dim=-1)
        actions = torch.where(
            placements.any(dim=-1), first, torch.full_like(first, 4 * 18 * 32)
        )
        step = bridge.step(
            actions,
            public_action_masks=actual,
            public_action_mask_contract_version=2,
        )
        bridge.reset_done(step.done)

    source = inspect.getsource(SimplePublicMaskV2Provider.build)
    for forbidden in (".cpu(", ".numpy(", ".item(", ".tolist("):
        assert forbidden not in source


def _assert_tensor_fields_equal(left: Any, right: Any) -> None:
    assert type(left) is type(right)
    for descriptor in fields(left):
        left_value = getattr(left, descriptor.name)
        right_value = getattr(right, descriptor.name)
        if isinstance(left_value, torch.Tensor):
            assert torch.equal(left_value, right_value), descriptor.name


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_graph_collector_matches_eager_real_recurrent_boundaries() -> None:
    graph = _training_collector(
        "cuda",
        batch_size=2,
        execution_mode=SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH,
    )
    eager = _training_collector(
        "cuda",
        batch_size=2,
        execution_mode=SIMPLE_PYTORCH_EXECUTION_EAGER,
    )
    eager.policy.model.load_state_dict(graph.policy.model.state_dict())
    graph.policy.model.eval()
    eager.policy.model.eval()
    graph_initial = graph.policy.model.initial_state(4, device="cuda")
    eager_initial = tuple(value.clone() for value in graph_initial)
    graph_recurrent = {
        "hidden": graph_initial[0].reshape(2, 2, -1),
        "cell": graph_initial[1].reshape(2, 2, -1),
    }
    eager_recurrent = {
        "hidden": eager_initial[0].reshape(2, 2, -1),
        "cell": eager_initial[1].reshape(2, 2, -1),
    }

    torch.manual_seed(91)
    graph_batch = graph.collector.collect(3, recurrent_inputs=graph_recurrent)
    torch.manual_seed(91)
    eager_batch = eager.collector.collect(3, recurrent_inputs=eager_recurrent)
    torch.cuda.synchronize()

    _assert_tensor_fields_equal(graph_batch.actor, eager_batch.actor)
    assert graph_batch.critic is not None and eager_batch.critic is not None
    _assert_tensor_fields_equal(graph_batch.critic, eager_batch.critic)
    for name in (
        "legal_masks",
        "public_action_masks",
        "previous_actions",
        "previous_rewards",
        "episode_starts",
        "actions",
        "rewards",
        "done",
        "winner",
        "action_success",
        "native_ticks",
        "committed",
        "fallback_rows",
        "all_rows_admitted",
        "reset_masks",
    ):
        assert torch.equal(getattr(graph_batch, name), getattr(eager_batch, name)), name
    assert graph_batch.recurrent_inputs is not None
    assert eager_batch.recurrent_inputs is not None
    for name in ("hidden", "cell"):
        assert torch.equal(
            graph_batch.recurrent_inputs[name], eager_batch.recurrent_inputs[name]
        )
        assert torch.equal(
            graph_batch.bootstrap.recurrent_inputs[name],
            eager_batch.bootstrap.recurrent_inputs[name],
        )
    for name in ("log_prob", "value"):
        assert torch.equal(
            graph_batch.policy_storage[name], eager_batch.policy_storage[name]
        )
    _assert_tensor_fields_equal(
        graph_batch.bootstrap.actor,
        eager_batch.bootstrap.actor,
    )
    assert graph_batch.bootstrap.critic is not None
    assert eager_batch.bootstrap.critic is not None
    _assert_tensor_fields_equal(
        graph_batch.bootstrap.critic,
        eager_batch.bootstrap.critic,
    )
    for name in (
        "legal_mask",
        "public_action_masks",
        "previous_actions",
        "previous_rewards",
        "episode_starts",
    ):
        assert torch.equal(
            getattr(graph_batch.bootstrap, name),
            getattr(eager_batch.bootstrap, name),
        ), name
    assert graph_batch.metadata == eager_batch.metadata


def test_integrated_actor_v2_mask_exposes_archer_queen_ability() -> None:
    collector = _training_collector(batch_size=7)
    bridge = collector.collector.bridge
    adapter = collector.collector.public_mask_provider
    vocabulary = load_current_client_typed_vocabulary()
    queen_action = vocabulary.resolve("ArcherQueen", "card_action")
    queen_body = vocabulary.resolve("ArcherQueen", "troop_body")
    assert queen_action > 1 and queen_body > 1
    assert collector.public_mask_tables.ability_supported[queen_body]
    assert collector.public_mask_tables.ability_elixir_cost[queen_body] == 1.0

    observation = bridge.observe()
    locations = (observation.actor.hand_ids[..., :4] == queen_action).nonzero()
    assert locations.shape[0] == 1
    batch, seat, slot = (int(value) for value in locations[0])
    public_mask = adapter(SimpleTensorMaskRequest(observation, 0, False)).masks
    placements = public_mask[batch, seat, slot * 18 * 32 : (slot + 1) * 18 * 32]
    assert placements.any()
    actions = torch.full(
        (collector.batch_size, 2),
        NO_OP_ACTION,
        dtype=torch.int64,
        device=observation.actor.hand_ids.device,
    )
    actions[batch, seat] = slot * 18 * 32 + int(placements.to(torch.int64).argmax())
    bridge.step(
        actions,
        public_action_masks=public_mask,
        public_action_mask_contract_version=2,
    )

    became_legal = False
    for decision_index in range(1, 65):
        observation = bridge.observe()
        public_mask = adapter(
            SimpleTensorMaskRequest(observation, decision_index, False)
        ).masks
        assert (
            public_mask[batch, seat, ABILITY_ACTION]
            == (observation.legal_mask[batch, seat, ABILITY_ACTION])
        )
        if public_mask[batch, seat, ABILITY_ACTION]:
            became_legal = True
            break
        actions.fill_(NO_OP_ACTION)
        bridge.step(
            actions,
            public_action_masks=public_mask,
            public_action_mask_contract_version=2,
        )
    assert became_legal
