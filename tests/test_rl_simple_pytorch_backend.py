from __future__ import annotations

import inspect
from argparse import Namespace
from dataclasses import fields, replace
from typing import Any

import numpy as np
import pytest
import torch

import clasher.rl.simple_pytorch_backend as simple_backend
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.simple_pytorch_backend import (
    SIMPLE_PYTORCH_BACKEND,
    SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH,
    SIMPLE_PYTORCH_EXECUTION_EAGER,
    SimplePytorchBackendError,
    SimplePytorchTrainingCollector,
    _CoalescedCpuStaging,
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
    if device_name == "mps" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
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
    expected_layout = {
        "entity_ids": ((2, 1, 128), np.dtype(np.int64)),
        "entity_features": ((2, 1, 128, 32), np.dtype(np.float32)),
        "entity_mask": ((2, 1, 128), np.dtype(np.bool_)),
        "hand_ids": ((2, 1, 5), np.dtype(np.int64)),
        "global_features": ((2, 1, 18), np.dtype(np.float32)),
        "entity_id_confidence": ((2, 1, 128), np.dtype(np.float32)),
        "entity_feature_confidence": ((2, 1, 128, 32), np.dtype(np.float32)),
        "hand_id_confidence": ((2, 1, 5), np.dtype(np.float32)),
        "global_feature_confidence": ((2, 1, 18), np.dtype(np.float32)),
        "action_masks": ((2, 1, model.num_actions), np.dtype(np.bool_)),
        "previous_actions": ((2, 1), np.dtype(np.int64)),
        "previous_rewards": ((2, 1), np.dtype(np.float32)),
        "episode_starts": ((2, 1), np.dtype(np.bool_)),
        "critic_entity_ids": ((2, 1, 128), np.dtype(np.int64)),
        "critic_entity_features": ((2, 1, 128, 32), np.dtype(np.float32)),
        "critic_entity_mask": ((2, 1, 128), np.dtype(np.bool_)),
        "critic_card_ids": ((2, 1, 10), np.dtype(np.int64)),
        "critic_global_features": ((2, 1, 20), np.dtype(np.float32)),
        "actions": ((2, 1), np.dtype(np.int64)),
        "old_log_probs": ((2, 1), np.dtype(np.float32)),
        "old_values": ((2, 1), np.dtype(np.float32)),
        "rewards": ((2, 1), np.dtype(np.float32)),
        "dones": ((2, 1), np.dtype(np.bool_)),
        "initial_hidden": ((2, 32), np.dtype(np.float32)),
        "initial_cell": ((2, 32), np.dtype(np.float32)),
        "bootstrap_values": ((2,), np.dtype(np.float32)),
    }
    for name, (shape, dtype) in expected_layout.items():
        assert arrays[name].shape == shape, name
        assert arrays[name].dtype == dtype, name
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


def test_training_backend_builds_six_way_public_terminal_counterfactuals() -> None:
    collector = _training_collector()
    evaluator = collector.create_terminal_counterfactual_evaluator(
        6,
        terminal_check_interval=1,
        strict_host_validation=True,
    )
    assert collector.collector.bridge.observe().critic is not None
    assert evaluator.bridge.observe().critic is None
    source = collector.collector.bridge
    source.runtime.state.tick.fill_(5_996)
    candidates = torch.full(
        (1, 6, 2),
        NO_OP_ACTION,
        dtype=torch.int64,
        device=source.device,
    )
    hidden, cell = collector.policy.model.initial_state(2, device=source.device)
    recurrent = {
        "hidden": hidden.reshape(1, 2, -1),
        "cell": cell.reshape(1, 2, -1),
    }

    result = evaluator.evaluate(
        source,
        candidates,
        learner_players=torch.zeros(1, dtype=torch.int64, device=source.device),
        recurrent_inputs=recurrent,
        max_decisions=2,
    )

    assert result.flat_candidates == 6
    assert result.root_actor.entity_ids.shape == (6, 2, 128)
    assert result.root_actor.entity_features.shape == (6, 2, 128, 32)
    assert result.root_actor.hand_ids.shape == (6, 2, 5)
    assert result.root_actor.global_features.shape == (6, 2, 18)
    assert result.root_public_action_masks.shape == (
        6,
        2,
        collector.policy.model.num_actions,
    )
    assert result.terminal_winner.lt(0).all()
    assert result.terminal_value.eq(0.0).all()
    assert result.native_ticks.eq(4).all()
    assert result.committed.all()
    assert result.all_rows_admitted.all()
    assert not result.fallback_rows.any()


def test_cpu_coalesced_handoff_preserves_shapes_dtypes_and_values() -> None:
    source = {
        "float": torch.arange(24, dtype=torch.float32).reshape(2, 3, 4).transpose(0, 1),
        "integer": torch.arange(10, dtype=torch.int64).reshape(2, 5),
        "boolean": (torch.arange(12).reshape(3, 4) % 3) == 0,
        "empty": torch.empty((2, 0, 3), dtype=torch.float32),
    }
    expected = {name: value.numpy().copy() for name, value in source.items()}

    actual = _CoalescedCpuStaging(source).finish()

    assert set(actual) == set(expected)
    for name, expected_value in expected.items():
        assert actual[name].shape == expected_value.shape
        assert actual[name].dtype == expected_value.dtype
        assert np.array_equal(actual[name], expected_value)
        assert not np.shares_memory(actual[name], expected_value)


def test_training_handoff_has_no_per_tensor_blocking_transfer() -> None:
    source = inspect.getsource(SimplePytorchTrainingCollector.collect)
    for forbidden in (".cpu(", ".numpy(", ".item("):
        assert forbidden not in source
    staging_source = inspect.getsource(_CoalescedCpuStaging)
    assert "non_blocking=True" in staging_source
    assert staging_source.count("_synchronize_cuda_stream(") == 1


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_coalesced_handoff_matches_blocking_with_one_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = {
        "float": torch.arange(24, dtype=torch.float32, device="cuda")
        .reshape(2, 3, 4)
        .transpose(0, 1),
        "integer": torch.arange(10, dtype=torch.int64, device="cuda").reshape(2, 5),
        "boolean": (torch.arange(12, device="cuda").reshape(3, 4) % 3) == 0,
        "empty": torch.empty((2, 0, 3), dtype=torch.float32, device="cuda"),
    }
    expected = {name: value.cpu().numpy() for name, value in source.items()}
    calls = 0
    original = simple_backend._synchronize_cuda_stream

    def counted(stream: torch.cuda.Stream) -> None:
        nonlocal calls
        calls += 1
        original(stream)

    monkeypatch.setattr(simple_backend, "_synchronize_cuda_stream", counted)
    actual = _CoalescedCpuStaging(source).finish()

    assert calls == 1
    for name, expected_value in expected.items():
        assert actual[name].shape == expected_value.shape
        assert actual[name].dtype == expected_value.dtype
        assert np.array_equal(actual[name], expected_value)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_training_wrapper_uses_one_handoff_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = _training_collector("cuda", batch_size=2)
    model = collector.policy.model
    calls = 0
    original = simple_backend._synchronize_cuda_stream

    def counted(stream: torch.cuda.Stream) -> None:
        nonlocal calls
        calls += 1
        original(stream)

    monkeypatch.setattr(simple_backend, "_synchronize_cuda_stream", counted)
    arrays, next_state, previous_actions, previous_rewards, episode_starts = (
        collector.collect(2, model.initial_state(4, device="cuda"))
    )

    assert calls == 1
    rollout = RolloutBatch(**arrays)
    assert rollout.transitions == 8
    assert rollout.action_masks[
        np.arange(4)[:, None], np.arange(2)[None, :], rollout.actions
    ].all()
    assert next_state[0].shape == next_state[1].shape == (4, 32)
    assert (
        previous_actions.shape == previous_rewards.shape == episode_starts.shape == (4,)
    )


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


@pytest.mark.parametrize("device_name", ("cpu", "cuda", "mps"))
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


@pytest.mark.skipif(
    not torch.backends.mps.is_available(),
    reason="MPS unavailable",
)
def test_mps_training_wrapper_collects_one_recurrent_decision() -> None:
    collector = _training_collector("mps")
    model = collector.policy.model

    arrays, next_state, previous_actions, previous_rewards, episode_starts = (
        collector.collect(1, model.initial_state(2, device="mps"))
    )
    torch.mps.synchronize()

    assert collector.metadata.execution_mode == SIMPLE_PYTORCH_EXECUTION_EAGER
    assert arrays["actions"].shape == (2, 1)
    assert arrays["action_masks"].shape == (2, 1, model.num_actions)
    assert arrays["action_masks"][
        torch.arange(2).numpy(), 0, arrays["actions"][:, 0]
    ].all()
    assert next_state[0].device.type == "mps"
    assert next_state[1].device.type == "mps"
    assert previous_actions.shape == (2,)
    assert previous_rewards.shape == (2,)
    assert episode_starts.shape == (2,)

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
