from __future__ import annotations

import inspect
from argparse import Namespace
from dataclasses import fields, replace
from typing import Any

import numpy as np
import pytest
import torch

import clasher.rl.simple_pytorch_backend as simple_backend
from clasher.arena import Position
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.simple_pytorch_backend import (
    SIMPLE_PYTORCH_BACKEND,
    SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH,
    SIMPLE_PYTORCH_EXECUTION_EAGER,
    SimplePytorchBackendError,
    SimplePytorchTrainingCollector,
    SimpleTensorStrategyOpponent,
    _CoalescedCpuStaging,
    load_current_client_typed_vocabulary,
    load_simple_supported_decks,
)
from clasher.rl.simple_tensor_collector import (
    SimpleTensorMaskRequest,
    SimpleTensorPolicyBoundary,
)
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import (
    RolloutBatch,
    _load_initial_policy_state,
    _validate_simple_initial_policy_contract,
    _validate_simple_pytorch_args,
)
from clasher.torch_sim.actions import ABILITY_ACTION, NO_OP_ACTION
from clasher.torch_sim.resident_outputs import TensorPublicStructuredObservation
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
        "initialize_policy_from": None,
        "opponent_mode": "selfplay",
        "opponent_checkpoint": [],
        "opponent_strategy": None,
        "league_opponent": [],
        "pfsp_report": None,
        "pfsp_strategy_workers": None,
        "mirror_match": False,
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
        "simple_max_entities": 128,
        "simple_max_effects": 128,
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


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"simple_max_entities": 15}, "simple-max-entities"),
        ({"simple_max_effects": 0}, "simple-max-effects"),
    ),
)
def test_simple_backend_capacity_arguments_fail_closed(
    overrides: dict[str, int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _validate_simple_pytorch_args(_simple_args(**overrides))


def test_simple_initial_policy_is_weights_only_and_capacity_exact(
    tmp_path: Any,
) -> None:
    vocabulary = load_current_client_typed_vocabulary()
    config = PolicyConfig(
        num_tokens=len(vocabulary.token_names),
        max_entities=48,
        canonical_lane_globals=True,
        card_semantics_version=3,
        actor_observation_domain="causal-frame-v1",
        public_observation_confidence=True,
        memory_kind="structured",
        memory_size=64,
    )
    path = tmp_path / "imitation.pt"
    torch.save(
        {
            "format_version": 2,
            "model_type": "entity_spatial_recurrent",
            "model_config": config.to_dict(),
            "model_state_dict": {"weight": torch.ones(1)},
            "token_names": vocabulary.token_names,
            "optimizer_state_dict": {"must_not_load": True},
            "update": 91,
            "total_transitions": 123_456,
        },
        path,
    )
    payload, loaded_path = _load_initial_policy_state(
        _simple_args(initialize_policy_from=str(path)), torch.device("cpu")
    )
    assert payload is not None
    assert loaded_path == path.resolve()
    assert _validate_simple_initial_policy_contract(
        payload,
        token_names=vocabulary.token_names,
        max_entities=48,
    ) == config
    lifted = _validate_simple_initial_policy_contract(
        payload,
        token_names=vocabulary.token_names,
        max_entities=64,
    )
    assert lifted == replace(config, max_entities=64)
    shrunk = _validate_simple_initial_policy_contract(
        payload,
        token_names=vocabulary.token_names,
        max_entities=47,
    )
    assert shrunk == replace(config, max_entities=47)


def test_simple_initial_policy_rejects_resume_combination(tmp_path: Any) -> None:
    path = tmp_path / "imitation.pt"
    path.write_bytes(b"not-loaded")
    with pytest.raises(ValueError, match="cannot be combined"):
        _load_initial_policy_state(
            _simple_args(
                initialize_policy_from=str(path),
                resume_from="other.pt",
            ),
            torch.device("cpu"),
        )


def _training_collector(
    device_name: str = "cpu",
    *,
    batch_size: int = 1,
    execution_mode: str | None = None,
    max_entities: int = 128,
    max_effects: int = 128,
    actor_observation_domain: str = "simulator-exact",
    opponent_mode: str = "selfplay",
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
        max_entities=max_entities,
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
        actor_observation_domain=actor_observation_domain,
        public_observation_confidence=(
            actor_observation_domain in {"causal-frame-v1", "causal-vision-v1"}
        ),
    )
    model = ClasherPolicy(config, builder.card_stat_features).to(device)
    opponent_model = None
    opponent_sha256 = None
    if opponent_mode == "checkpoint":
        opponent_model = ClasherPolicy(config, builder.card_stat_features).to(device)
        opponent_model.load_state_dict(model.state_dict())
        opponent_sha256 = "f" * 64
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
        opponent_mode=opponent_mode,
        opponent_model=opponent_model,
        opponent_checkpoint_sha256=opponent_sha256,
        opponent_strategy=("balanced" if opponent_mode == "strategy" else None),
        opponent_strategy_schedule=(
            ("bridge-pressure", "slow-push")
            if opponent_mode == "league"
            else ()
        ),
        learner_deck_name="Hog 2.6 Cycle",
        max_effects=max_effects,
        _execution_mode_override=execution_mode,
    )


def test_simple_backend_accepts_causal_frame_policy_but_not_stabilized_vision() -> None:
    collector = _training_collector(actor_observation_domain="causal-frame-v1")
    assert collector.policy.model.config.public_observation_confidence
    with pytest.raises(SimplePytorchBackendError, match="policy input"):
        _training_collector(actor_observation_domain="causal-vision-v1")


@pytest.mark.parametrize("device_name", ("cpu", "mps", "cuda"))
def test_capacity_is_explicit_in_shapes_and_checkpoint_contract(
    device_name: str,
) -> None:
    collector = _training_collector(device_name, max_entities=48, max_effects=64)
    model = collector.policy.model
    arrays, _next_state, _previous_actions, _previous_rewards, _episode_starts = (
        collector.collect(1, model.initial_state(2, device=device_name))
    )
    assert arrays["entity_ids"].shape == (2, 1, 48)
    assert arrays["critic_entity_ids"].shape == (2, 1, 48)
    metadata = collector.checkpoint_metadata()
    assert metadata["max_entities"] == 48
    assert metadata["max_effects"] == 64


def test_policy_outputs_are_entity_capacity_metadata_invariant() -> None:
    collector = _training_collector(max_entities=48, max_effects=64)
    narrow = collector.policy.model.eval()
    wide_config = replace(narrow.config, max_entities=128)
    vocabulary = load_current_client_typed_vocabulary()
    builder = StructuredObservationBuilder(
        decks_path="decks.json",
        token_names=vocabulary.token_names,
        max_entities=48,
        canonical_lane_globals=True,
    )
    wide = ClasherPolicy(wide_config, builder.card_stat_features).eval()
    wide.load_state_dict(narrow.state_dict())
    observation = collector.collector.bridge.observe()
    packet = collector.collector.public_mask_provider(
        SimpleTensorMaskRequest(observation, decision_index=0, bootstrap=False)
    )
    boundary = SimpleTensorPolicyBoundary(
        actor=observation.actor,
        critic=observation.critic,
        legal_mask=observation.legal_mask,
        public_action_masks=packet.masks,
        previous_actions=observation.previous_actions,
        previous_rewards=observation.previous_rewards,
        episode_starts=observation.episode_starts,
        recurrent_inputs={
            "hidden": torch.zeros((1, 2, 32)),
            "cell": torch.zeros((1, 2, 32)),
        },
        decision_index=0,
    )
    inputs = collector.policy.inputs(boundary)
    state = collector.policy.state_from_mapping(boundary.recurrent_inputs)
    assert state is not None
    with torch.no_grad():
        narrow_output = narrow.forward(inputs, state)
        wide_output = wide.forward(inputs, state)
    assert torch.equal(narrow_output.action_type_logits, wide_output.action_type_logits)
    assert torch.equal(narrow_output.location_logits, wide_output.location_logits)
    assert torch.equal(narrow_output.values, wide_output.values)


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


@pytest.mark.parametrize(
    "opponent_mode", ("noop", "random", "strategy", "league", "checkpoint")
)
def test_stationary_simple_backend_exports_only_learner_rows(
    opponent_mode: str,
) -> None:
    collector = _training_collector(
        batch_size=4,
        max_entities=48,
        max_effects=64,
        opponent_mode=opponent_mode,
    )
    model = collector.policy.model
    torch.manual_seed(1163501)
    arrays, next_state, previous_actions, previous_rewards, episode_starts = (
        collector.collect(2, model.initial_state(4, device="cpu"))
    )
    rollout = RolloutBatch(**arrays)

    assert rollout.actions.shape == (4, 2)
    assert rollout.transitions == 8
    assert rollout.action_masks[
        np.arange(4)[:, None], np.arange(2)[None, :], rollout.actions
    ].all()
    assert next_state[0].shape == next_state[1].shape == (4, 32)
    assert (
        previous_actions.shape
        == previous_rewards.shape
        == episode_starts.shape
        == (4,)
    )
    metadata = collector.checkpoint_metadata()
    assert metadata["learner_only"] is True
    assert metadata["opponent_mode"] == opponent_mode
    assert metadata["learner_deck_name"] == "Hog 2.6 Cycle"
    assert metadata["learner_players"] == (0, 1, 0, 1)
    assert len(metadata["opponent_deck_names"]) == 4
    assert metadata["opponent_deck_names"][0] == metadata["opponent_deck_names"][1]
    assert metadata["opponent_deck_names"][2] == metadata["opponent_deck_names"][3]
    assert bool(metadata["opponent_checkpoint_sha256"]) == (
        opponent_mode == "checkpoint"
    )
    assert metadata["opponent_strategy"] == (
        "balanced" if opponent_mode == "strategy" else None
    )
    assert bool(metadata["opponent_strategy_schedule"]) == (
        opponent_mode == "league"
    )
    if opponent_mode == "league":
        assert metadata["opponent_strategy_schedule"] == (
            "bridge-pressure",
            "slow-push",
            "bridge-pressure",
            "slow-push",
        )

    current = collector.collector.bridge.observe().previous_actions
    rows = torch.arange(4)
    opponent_players = 1 - collector.learner_players
    opponent_actions = current[rows, opponent_players]
    if opponent_mode == "noop":
        assert torch.equal(
            opponent_actions,
            torch.full_like(opponent_actions, NO_OP_ACTION),
        )
    elif opponent_mode == "random":
        assert bool((opponent_actions != NO_OP_ACTION).any().item())


def test_simple_argument_gate_accepts_stationary_modes_fail_closed() -> None:
    _validate_simple_pytorch_args(_simple_args(opponent_mode="noop"))
    _validate_simple_pytorch_args(_simple_args(opponent_mode="random"))
    _validate_simple_pytorch_args(
        _simple_args(opponent_mode="strategy", opponent_strategy="balanced")
    )
    _validate_simple_pytorch_args(
        _simple_args(
            opponent_mode="league",
            league_opponent=[
                "strategy:bridge-pressure",
                "strategy:slow-push",
            ],
        )
    )
    _validate_simple_pytorch_args(
        _simple_args(
            opponent_mode="checkpoint",
            opponent_checkpoint=["frozen.pt"],
        )
    )
    with pytest.raises(ValueError, match="exactly one frozen checkpoint"):
        _validate_simple_pytorch_args(
            _simple_args(opponent_mode="checkpoint", opponent_checkpoint=[])
        )
    with pytest.raises(ValueError, match="asymmetric deck rows"):
        _validate_simple_pytorch_args(
            _simple_args(opponent_mode="random", mirror_match=True)
        )
    _validate_simple_pytorch_args(
        _simple_args(opponent_mode="league", pfsp_report="pfsp.json")
    )
    with pytest.raises(ValueError, match="at least two explicit strategy"):
        _validate_simple_pytorch_args(
            _simple_args(
                opponent_mode="league",
                league_opponent=["strategy:balanced"],
            )
        )


def test_strategy_league_rollout_is_exactly_replayable() -> None:
    first = _training_collector(
        batch_size=4,
        max_entities=48,
        max_effects=64,
        opponent_mode="league",
    )
    second = _training_collector(
        batch_size=4,
        max_entities=48,
        max_effects=64,
        opponent_mode="league",
    )
    torch.manual_seed(1163603)
    first_arrays, first_state, *first_boundary = first.collect(
        3, first.policy.model.initial_state(4, device="cpu")
    )
    torch.manual_seed(1163603)
    second_arrays, second_state, *second_boundary = second.collect(
        3, second.policy.model.initial_state(4, device="cpu")
    )

    assert set(first_arrays) == set(second_arrays)
    for name in first_arrays:
        first_value = first_arrays[name]
        second_value = second_arrays[name]
        if isinstance(first_value, np.ndarray):
            assert np.array_equal(first_value, second_value), name
        else:
            assert first_value == second_value, name
    assert torch.equal(first_state[0], second_state[0])
    assert torch.equal(first_state[1], second_state[1])
    for first_value, second_value in zip(
        first_boundary, second_boundary, strict=True
    ):
        assert np.array_equal(first_value, second_value)


@pytest.mark.parametrize("strategy_name", STRATEGY_NAMES)
def test_tensor_strategy_matches_python_on_initial_public_states(
    strategy_name: str,
) -> None:
    collector = _training_collector(
        batch_size=2,
        max_entities=48,
        max_effects=64,
        opponent_mode="strategy",
    )
    observation = collector.collector.bridge.observe()
    packet = collector.collector.public_mask_provider(
        SimpleTensorMaskRequest(observation, decision_index=0, bootstrap=False)
    )
    boundary = SimpleTensorPolicyBoundary(
        actor=observation.actor,
        critic=observation.critic,
        legal_mask=observation.legal_mask,
        public_action_masks=packet.masks,
        previous_actions=observation.previous_actions,
        previous_rewards=observation.previous_rewards,
        episode_starts=observation.episode_starts,
        recurrent_inputs=None,
        decision_index=0,
    )
    vocabulary = load_current_client_typed_vocabulary()
    builder = StructuredObservationBuilder(
        decks_path="decks.json",
        token_names=vocabulary.token_names,
        max_entities=48,
        canonical_lane_globals=True,
    )
    tensor_strategy = SimpleTensorStrategyOpponent(
        builder,
        strategy_name=strategy_name,
        device=torch.device("cpu"),
    )
    tensor_actions = tensor_strategy(boundary)

    for row in range(2):
        for seat in (0, 1):
            env = SelfPlayBattleEnv(
                decks_path="decks.json",
                seed=1163601 + 10 * row + seat,
                canonical_perspective=True,
                canonical_lane_globals=True,
            )
            env.reset(seed=1163601 + 10 * row + seat)
            assert env.battle is not None
            hand_ids = observation.actor.hand_ids[row, seat, :4].tolist()
            hand = [builder.card_name_for_token_id(int(token)) for token in hand_ids]
            assert all(name is not None for name in hand)
            env.battle.players[seat].hand = hand  # type: ignore[assignment]
            env.battle.players[seat].elixir = float(
                observation.actor.global_features[row, seat, 5] * 10.0
            )
            expected = StrategyBot(strategy_name).select_action(
                env,
                seat,
                action_mask=packet.masks[row, seat].numpy(),
            )
            assert int(tensor_actions[row, seat]) == expected


@pytest.mark.parametrize("strategy_name", STRATEGY_NAMES)
def test_tensor_strategy_matches_python_with_visible_pressure(
    strategy_name: str,
) -> None:
    vocabulary = load_current_client_typed_vocabulary()
    builder = StructuredObservationBuilder(
        decks_path="decks.json",
        token_names=vocabulary.token_names,
        max_entities=48,
        canonical_lane_globals=True,
    )
    env = SelfPlayBattleEnv(
        decks_path="decks.json",
        seed=1163602,
        canonical_perspective=True,
        canonical_lane_globals=True,
    )
    env._structured_obs_builder = builder
    env.reset(seed=1163602)
    assert env.battle is not None
    env.battle.players[0].hand = ["Musketeer", "Cannon", "Fireball", "HogRider"]
    env.battle.players[1].hand = ["Giant", "Minions", "Fireball", "MiniPekka"]
    env.battle.players[0].elixir = 10.0
    env.battle.players[1].elixir = 10.0
    p0_action = env.action_space.encode_action(3, 4, 14, 0)
    p1_action = env.action_space.encode_action(0, 13, 17, 1)
    assert env.action_space.apply_action(env.battle, 0, p0_action)
    assert env.action_space.apply_action(env.battle, 1, p1_action)
    combat = [
        entity
        for entity in env.battle.entities.values()
        if getattr(entity, "entity_kind", -1) == 0
    ]
    p0_troop = next(entity for entity in combat if entity.player_id == 0)
    p1_troop = next(entity for entity in combat if entity.player_id == 1)
    p0_troop.position = Position(13.5, 20.5)
    p1_troop.position = Position(4.5, 11.5)
    for entity in (p0_troop, p1_troop):
        entity.placement_pending = False
        entity.deploy_delay_remaining = 0.0
    env.battle.players[0].hand = ["Musketeer", "Cannon", "Fireball", "HogRider"]
    env.battle.players[1].hand = ["Giant", "Minions", "Fireball", "MiniPekka"]
    env.battle.players[0].elixir = 10.0
    env.battle.players[1].elixir = 10.0

    observations = [builder.build(env.battle, seat) for seat in (0, 1)]
    actor = TensorPublicStructuredObservation(
        entity_ids=torch.as_tensor(
            np.stack([value.entity_ids for value in observations])[None, ...]
        ),
        entity_features=torch.as_tensor(
            np.stack([value.entity_features for value in observations])[None, ...]
        ),
        entity_mask=torch.as_tensor(
            np.stack([value.entity_mask for value in observations])[None, ...]
        ),
        hand_ids=torch.as_tensor(
            np.stack([value.hand_ids for value in observations])[None, ...]
        ),
        global_features=torch.as_tensor(
            np.stack([value.global_features for value in observations])[None, ...]
        ),
    )
    masks = torch.as_tensor(
        np.stack([env.get_action_mask(seat) for seat in (0, 1)])[None, ...]
    )
    boundary = SimpleTensorPolicyBoundary(
        actor=actor,
        critic=None,
        legal_mask=masks,
        public_action_masks=masks,
        previous_actions=torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64),
        previous_rewards=torch.zeros((1, 2), dtype=torch.float32),
        episode_starts=torch.zeros((1, 2), dtype=torch.bool),
        recurrent_inputs=None,
        decision_index=0,
    )
    actual = SimpleTensorStrategyOpponent(
        builder,
        strategy_name=strategy_name,
        device=torch.device("cpu"),
    )(boundary)
    for seat in (0, 1):
        expected = StrategyBot(strategy_name).select_action(
            env,
            seat,
            action_mask=masks[0, seat].numpy(),
        )
        assert int(actual[0, seat]) == expected


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
