from __future__ import annotations

import inspect
from argparse import Namespace

import pytest
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.simple_pytorch_backend import (
    SIMPLE_PYTORCH_BACKEND,
    ReferenceSimplePublicMaskV2Adapter,
    SimplePublicMaskV2Adapter,
    SimplePytorchTrainingCollector,
    load_current_client_typed_vocabulary,
    load_simple_supported_decks,
)
from clasher.rl.simple_tensor_collector import SimpleTensorMaskRequest
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import RolloutBatch, _validate_simple_pytorch_args


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


def _training_collector(device_name: str = "cpu") -> SimplePytorchTrainingCollector:
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
        batch_size=1,
        device=device,
        decision_interval=2,
        gamma=0.995,
        supported_decks_path="training_decks/simple_gym_supported_v1.json",
        typed_vocabulary_path=(
            "reports/current_client_youtube_stable_vocabulary_v1.json"
        ),
        mirror_match=False,
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
    assert rollout.action_masks[
        torch.arange(2).numpy(), 0, rollout.actions[:, 0]
    ].all()
    assert next_state[0].shape == (2, 32)
    assert previous_actions.shape == previous_rewards.shape == episode_starts.shape == (
        2,
    )
    metadata = collector.checkpoint_metadata()
    assert metadata["public_action_mask_contract_version"] == 2
    assert metadata["reward_contract_id"] == "objective-v1-gamma-v1"
    assert metadata["fresh_only"] is True


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_tensor_public_mask_matches_authoritative_trace(device_name: str) -> None:
    collector = _training_collector(device_name)
    bridge = collector.collector.bridge
    # Both adapters consume the exact same actor-only boundary. The reference
    # intentionally round-trips to NumPy; the production path must not.
    structured_builder = collector.collector.public_mask_provider.builder
    assert isinstance(structured_builder, StructuredObservationBuilder)
    tensor = SimplePublicMaskV2Adapter(structured_builder)
    reference = ReferenceSimplePublicMaskV2Adapter(structured_builder)

    for decision_index in range(4):
        observation = bridge.observe()
        request = SimpleTensorMaskRequest(observation, decision_index, False)
        actual = tensor(request).masks
        expected = reference(request).masks
        assert torch.equal(actual, expected)
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

    source = inspect.getsource(SimplePublicMaskV2Adapter.__call__)
    for forbidden in (".cpu(", ".numpy(", ".item(", ".tolist("):
        assert forbidden not in source
