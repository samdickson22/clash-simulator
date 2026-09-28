from unittest.mock import patch
import math
from collections import deque
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest
import torch
from torch import nn

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl import train_recurrent as train_recurrent_module
from clasher.rl.model import (
    ClasherPolicy,
    PolicyConfig,
    PolicyInputs,
    PolicyOutput,
    PrototypeRepairAdapter,
)
from clasher.rl.parallel_rollout import concatenate_rollouts
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import (
    _stack_step_inputs,
    collect_rollout,
    collect_rollout_stationary_opponents,
    compute_gae,
    factorized_policy_anchor_kl,
    parameter_anchor_l2,
    policy_anchor_kl,
    ppo_update,
)


def _tiny_model(builder: StructuredObservationBuilder) -> ClasherPolicy:
    return ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=48,
        ),
        builder.card_stat_features,
    )


def test_policy_config_normalizes_per_stage_prototype_thresholds():
    config = PolicyConfig.from_dict(
        {
            "num_tokens": 4,
            "max_entities": 8,
            "repair_stage_sizes": [8, 8],
            "repair_stage_prototype_counts": [1, 1],
            "repair_stage_prototype_thresholds": [0.99999, 0.999],
            "repair_stage_prototype_guard_counts": [0, 1],
            "repair_stage_prototype_guard_thresholds": [0.99999, 0.99999],
            "repair_stage_prototype_hard_guards": [False, True],
            "repair_stage_yield_to_prior": [False, True],
        }
    )

    assert config.repair_stage_sizes == (8, 8)
    assert config.repair_stage_prototype_counts == (1, 1)
    assert config.repair_stage_prototype_thresholds == (0.99999, 0.999)
    assert config.repair_stage_prototype_guard_counts == (0, 1)
    assert config.repair_stage_prototype_guard_thresholds == (0.99999, 0.99999)
    assert config.repair_stage_prototype_hard_guards == (False, True)
    assert config.repair_stage_yield_to_prior == (False, True)


@pytest.mark.parametrize(
    ("encoder_kind", "decoder_kind", "memory_kind", "card_input_mode"),
    [
        ("attention", "attention", "lstm", "hybrid"),
        ("attention", "global", "lstm", "residual-hybrid"),
        ("deepsets", "attention", "lstm", "hybrid"),
        ("deepsets", "global", "gru", "id-only"),
        ("deepsets", "global", "feedforward", "mechanics-only"),
    ],
)
def test_architecture_ablation_variants_forward(
    encoder_kind: str,
    decoder_kind: str,
    memory_kind: str,
    card_input_mode: str,
):
    env = SelfPlayBattleEnv(seed=103, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    env._structured_obs_builder = builder
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=48,
            encoder_kind=encoder_kind,
            decoder_kind=decoder_kind,
            memory_kind=memory_kind,
            card_input_mode=card_input_mode,
        ),
        builder.card_stat_features,
    ).eval()
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )

    with torch.no_grad():
        output = model(inputs)

    assert output.joint_logits.shape == (1, 1, model.num_actions)
    assert output.values.shape == (1, 1)
    assert torch.isfinite(output.joint_logits[inputs.action_mask]).all()
    assert bool((output.joint_logits[~inputs.action_mask] == -1e9).all())
    assert (model.actor_encoder.token_embedding is None) == (
        card_input_mode == "mechanics-only"
    )
    assert (model.actor_encoder.card_stat_projection is None) == (
        card_input_mode == "id-only"
    )
    if card_input_mode == "residual-hybrid":
        assert model.actor_encoder.card_stat_projection is not None
        residual_output = model.actor_encoder.card_stat_projection[-1]
        assert isinstance(residual_output, torch.nn.Linear)
        assert not bool(torch.count_nonzero(residual_output.weight))
        assert not bool(torch.count_nonzero(residual_output.bias))
    assert bool(model.actor_encoder.blocks) == (encoder_kind == "attention")
    assert (model.tile_decoder is not None) == (decoder_kind == "attention")


def test_public_observation_confidence_is_opt_in_and_zero_residual_upgrade():
    env = SelfPlayBattleEnv(seed=107, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    env._structured_obs_builder = builder
    legacy = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=48,
        ),
        builder.card_stat_features,
    ).eval()
    confidence_model = ClasherPolicy(
        replace(legacy.config, public_observation_confidence=True),
        builder.card_stat_features,
    ).eval()
    incompatible = confidence_model.load_state_dict(legacy.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert set(incompatible.missing_keys) == {
        "actor_encoder.card_confidence_projection.0.bias",
        "actor_encoder.card_confidence_projection.0.weight",
        "actor_encoder.card_confidence_projection.2.bias",
        "actor_encoder.card_confidence_projection.2.weight",
        "actor_encoder.entity_confidence_projection.0.bias",
        "actor_encoder.entity_confidence_projection.0.weight",
        "actor_encoder.entity_confidence_projection.2.bias",
        "actor_encoder.entity_confidence_projection.2.weight",
        "actor_encoder.global_confidence_projection.0.bias",
        "actor_encoder.global_confidence_projection.0.weight",
        "actor_encoder.global_confidence_projection.2.bias",
        "actor_encoder.global_confidence_projection.2.weight",
    }
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with pytest.raises(
        ValueError,
        match="confidence-aware encoder requires entity_id_confidence",
    ):
        confidence_model(inputs)

    confidence_inputs = replace(
        inputs,
        entity_id_confidence=torch.rand_like(inputs.entity_ids, dtype=torch.float32),
        entity_feature_confidence=torch.rand_like(inputs.entity_features),
        hand_id_confidence=torch.rand_like(inputs.hand_ids, dtype=torch.float32),
        global_feature_confidence=torch.rand_like(inputs.global_features),
    )
    with torch.no_grad():
        legacy_output = legacy(inputs)
        upgraded_output = confidence_model(confidence_inputs)
    assert torch.equal(legacy_output.joint_logits, upgraded_output.joint_logits)
    assert torch.equal(legacy_output.values, upgraded_output.values)

    projections = (
        confidence_model.actor_encoder.entity_confidence_projection,
        confidence_model.actor_encoder.card_confidence_projection,
        confidence_model.actor_encoder.global_confidence_projection,
    )
    for projection in projections:
        assert projection is not None
        first = projection[0]
        output = projection[2]
        assert isinstance(first, nn.Linear)
        assert isinstance(output, nn.Linear)
        nn.init.constant_(first.weight, 0.1)
        nn.init.constant_(first.bias, 0.02)
        nn.init.constant_(output.weight, 0.01)
        nn.init.constant_(output.bias, 0.03)
    zero_confidence_inputs = replace(
        confidence_inputs,
        entity_id_confidence=torch.zeros_like(confidence_inputs.entity_id_confidence),
        entity_feature_confidence=torch.zeros_like(
            confidence_inputs.entity_feature_confidence
        ),
        hand_id_confidence=torch.zeros_like(confidence_inputs.hand_id_confidence),
        global_feature_confidence=torch.zeros_like(
            confidence_inputs.global_feature_confidence
        ),
    )
    one_confidence_inputs = replace(
        confidence_inputs,
        entity_id_confidence=torch.ones_like(confidence_inputs.entity_id_confidence),
        entity_feature_confidence=torch.ones_like(
            confidence_inputs.entity_feature_confidence
        ),
        hand_id_confidence=torch.ones_like(confidence_inputs.hand_id_confidence),
        global_feature_confidence=torch.ones_like(
            confidence_inputs.global_feature_confidence
        ),
    )
    with torch.no_grad():
        zero_output = confidence_model(zero_confidence_inputs)
        one_output = confidence_model(one_confidence_inputs)
    assert not torch.equal(zero_output.joint_logits, one_output.joint_logits)
    assert torch.equal(one_output.joint_logits, legacy_output.joint_logits)
    assert torch.equal(one_output.values, legacy_output.values)


def test_feedforward_memory_does_not_depend_on_carried_state():
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=48,
            encoder_kind="deepsets",
            memory_kind="feedforward",
        ),
        builder.card_stat_features,
    )
    global_context = torch.randn((2, 3, 32))
    previous_actions = torch.full((2, 3), model.num_actions - 2, dtype=torch.long)
    previous_rewards = torch.randn((2, 3))
    episode_starts = torch.zeros((2, 3), dtype=torch.bool)
    random_state = (torch.randn((2, 48)), torch.randn((2, 48)))

    without_state, _ = model._run_memory(
        global_context,
        previous_actions,
        previous_rewards,
        episode_starts,
        None,
    )
    with_state, _ = model._run_memory(
        global_context,
        previous_actions,
        previous_rewards,
        episode_starts,
        random_state,
    )

    torch.testing.assert_close(with_state, without_state)


def test_structured_actor_excludes_hidden_enemy_cards_and_elixir():
    battle = BattleState()
    builder = StructuredObservationBuilder(
        card_vocab=["Knight", "Archers", "Giant", "Fireball", "Golem", "Zap"],
        max_entities=32,
    )
    before = builder.build(battle, 0)
    battle.players[1].elixir = 9.75
    battle.players[1].hand = ["Golem", "Zap", "Fireball", "Giant"]
    battle.players[1].cycle_queue = deque(["Archers", "Knight"])
    after = builder.build(battle, 0)

    np.testing.assert_array_equal(before.entity_ids, after.entity_ids)
    np.testing.assert_array_equal(before.entity_features, after.entity_features)
    np.testing.assert_array_equal(before.hand_ids, after.hand_ids)
    np.testing.assert_array_equal(before.global_features, after.global_features)
    assert not np.array_equal(before.critic_card_ids, after.critic_card_ids)
    assert before.critic_global_features[-2] != after.critic_global_features[-2]


def test_player_one_canonical_lane_globals_swap_left_and_right_towers():
    battle = BattleState()
    for player_id in (0, 1):
        battle._starting_tower_hps[player_id]["left"] = 1000.0
        battle._starting_tower_hps[player_id]["right"] = 1000.0
    battle.players[0].left_tower_hp = 100.0
    battle.players[0].right_tower_hp = 200.0
    battle.players[1].left_tower_hp = 300.0
    battle.players[1].right_tower_hp = 400.0
    legacy = StructuredObservationBuilder(
        card_vocab=["Knight"], max_entities=32, canonical_lane_globals=False
    )
    corrected = StructuredObservationBuilder(
        card_vocab=["Knight"], max_entities=32, canonical_lane_globals=True
    )

    legacy_p1 = legacy.build_actor(battle, 1).global_features
    corrected_p1 = corrected.build_actor(battle, 1).global_features
    corrected_p0 = corrected.build_actor(battle, 0).global_features

    assert legacy_p1[8:10].tolist() == pytest.approx([0.3, 0.4])
    assert legacy_p1[11:13].tolist() == pytest.approx([0.1, 0.2])
    assert corrected_p1[8:10].tolist() == pytest.approx([0.4, 0.3])
    assert corrected_p1[11:13].tolist() == pytest.approx([0.2, 0.1])
    assert corrected_p0[8:10].tolist() == pytest.approx([0.1, 0.2])
    assert corrected_p0[11:13].tolist() == pytest.approx([0.3, 0.4])


def test_structured_entities_do_not_overwrite_same_position():
    battle = BattleState()
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    battle._spawn_troop(Position(9.0, 10.0), 0, stats)
    battle._spawn_troop(Position(9.0, 10.0), 0, stats)
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=32)
    observation = builder.build(battle, 0)

    knight_id = builder.token_id("Knight")
    matching = observation.entity_mask & (observation.entity_ids == knight_id)
    assert int(matching.sum()) == 2
    np.testing.assert_array_equal(
        observation.entity_features[matching, :2],
        np.asarray([[0.5, 10.0 / 32.0], [0.5, 10.0 / 32.0]], dtype=np.float32),
    )


def test_hierarchical_joint_distribution_is_legal_and_not_tile_count_biased():
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = _tiny_model(builder)
    type_logits = torch.zeros((1, 1, 6))
    location_logits = torch.zeros((1, 1, 4, 576))
    mask = torch.zeros((1, 1, 2306), dtype=torch.bool)
    mask[..., 0] = True
    mask[..., 576 : 576 + 100] = True
    mask[..., 2304] = True

    joint = model._joint_action_logits(type_logits, location_logits, mask)
    probabilities = torch.distributions.Categorical(logits=joint).probs
    assert torch.all(probabilities.masked_select(~mask) == 0)
    torch.testing.assert_close(probabilities.sum(-1), torch.ones((1, 1)))
    slot_zero = probabilities[..., :576].sum(-1)
    slot_one = probabilities[..., 576:1152].sum(-1)
    no_op = probabilities[..., 2304]
    torch.testing.assert_close(slot_zero, slot_one)
    torch.testing.assert_close(slot_zero, no_op)


def test_hierarchical_entropy_separates_action_type_and_location():
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = _tiny_model(builder)
    type_logits = torch.zeros((1, 1, 6))
    location_logits = torch.zeros((1, 1, 4, 576))
    mask = torch.zeros((1, 1, 2306), dtype=torch.bool)
    mask[..., 0] = True
    mask[..., 576 : 576 + 100] = True
    mask[..., 2304] = True
    joint = model._joint_action_logits(type_logits, location_logits, mask)
    output = PolicyOutput(
        joint_logits=joint,
        values=torch.zeros((1, 1)),
        opponent_hand_logits=torch.zeros((1, 1, builder.spec.num_tokens)),
        opponent_elixir=torch.zeros((1, 1)),
        next_state=model.initial_state(1),
        action_type_logits=type_logits,
        location_logits=location_logits,
    )

    action_type_entropy, location_entropy = output.entropy_components()
    expected_type_entropy = torch.full((1, 1), torch.log(torch.tensor(3.0)))
    expected_location_entropy = torch.full((1, 1), torch.log(torch.tensor(100.0)) / 3.0)
    torch.testing.assert_close(action_type_entropy, expected_type_entropy)
    torch.testing.assert_close(location_entropy, expected_location_entropy)
    torch.testing.assert_close(
        action_type_entropy + location_entropy,
        output.distribution().entropy(),
    )
    torch.testing.assert_close(
        output.conditional_slot_entropy(),
        torch.full((1, 1), torch.log(torch.tensor(2.0))),
    )


@pytest.mark.parametrize("legal_slot_count", [0, 1])
def test_conditional_slot_entropy_is_zero_without_a_card_choice(
    legal_slot_count: int,
):
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = _tiny_model(builder)
    type_logits = torch.zeros((1, 1, 6))
    location_logits = torch.zeros((1, 1, 4, 576))
    mask = torch.zeros((1, 1, 2306), dtype=torch.bool)
    for slot in range(legal_slot_count):
        mask[..., slot * 576] = True
    mask[..., 2304] = True
    output = PolicyOutput(
        joint_logits=model._joint_action_logits(type_logits, location_logits, mask),
        values=torch.zeros((1, 1)),
        opponent_hand_logits=torch.zeros((1, 1, builder.spec.num_tokens)),
        opponent_elixir=torch.zeros((1, 1)),
        next_state=model.initial_state(1),
        action_type_logits=type_logits,
        location_logits=location_logits,
    )

    entropy = output.conditional_slot_entropy()

    assert bool(torch.isfinite(entropy).all())
    torch.testing.assert_close(entropy, torch.zeros((1, 1)))


def test_parameter_anchor_l2_tracks_frozen_parameter_distance():
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = _tiny_model(builder)
    anchor = tuple(parameter.detach().clone() for parameter in model.parameters())
    torch.testing.assert_close(parameter_anchor_l2(model, anchor), torch.tensor(0.0))

    first_parameter = next(model.parameters())
    with torch.no_grad():
        first_parameter.reshape(-1)[0].add_(2.0)
    torch.testing.assert_close(parameter_anchor_l2(model, anchor), torch.tensor(2.0))


def test_parameter_anchor_l2_excludes_parameters_absent_from_source_checkpoint():
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = _tiny_model(builder)
    parameters = tuple(model.parameters())
    anchor: tuple[torch.Tensor | None, ...] = (
        None,
        *(parameter.detach().clone() for parameter in parameters[1:]),
    )

    with torch.no_grad():
        parameters[0].reshape(-1)[0].add_(2.0)
    torch.testing.assert_close(parameter_anchor_l2(model, anchor), torch.tensor(0.0))

    with torch.no_grad():
        parameters[1].reshape(-1)[0].add_(2.0)
    torch.testing.assert_close(parameter_anchor_l2(model, anchor), torch.tensor(2.0))


def test_policy_anchor_kl_is_zero_for_match_and_positive_for_drift():
    anchor_logits = torch.tensor([[[1.0, 0.0, -1.0]]])
    torch.testing.assert_close(
        policy_anchor_kl(anchor_logits.clone(), anchor_logits), torch.tensor(0.0)
    )

    current_logits = torch.tensor([[[-1.0, 0.0, 1.0]]])
    assert float(policy_anchor_kl(current_logits, anchor_logits)) > 0.0


def test_policy_anchor_kl_rejects_mismatched_shapes():
    with np.testing.assert_raises_regex(ValueError, "matching shapes"):
        policy_anchor_kl(torch.zeros((1, 2)), torch.zeros((1, 3)))


def test_factorized_location_anchor_kl_only_tracks_legal_tile_geometry():
    def output(location_logits: torch.Tensor) -> PolicyOutput:
        zeros = torch.zeros((1, 1, 1))
        return PolicyOutput(
            joint_logits=torch.zeros((1, 1, 2306)),
            values=zeros,
            opponent_hand_logits=zeros,
            opponent_elixir=zeros,
            next_state=(zeros, zeros),
            action_type_logits=torch.zeros((1, 1, 6)),
            location_logits=location_logits,
        )

    anchor_locations = torch.zeros((1, 1, 4, 576))
    current_locations = anchor_locations.clone()
    mask = torch.zeros((1, 1, 2306), dtype=torch.bool)
    mask[..., 0] = True
    mask[..., 1] = True
    mask[..., 2304] = True

    current_locations[..., 0, 2] = 100.0  # Illegal tiles are ignored.
    torch.testing.assert_close(
        factorized_policy_anchor_kl(
            output(current_locations),
            output(anchor_locations),
            mask,
            component="location",
        ),
        torch.tensor(0.0),
    )

    current_locations[..., 0, 1] = 2.0
    assert (
        float(
            factorized_policy_anchor_kl(
                output(current_locations),
                output(anchor_locations),
                mask,
                component="location",
            )
        )
        > 0.0
    )
    torch.testing.assert_close(
        factorized_policy_anchor_kl(
            output(current_locations),
            output(anchor_locations),
            mask,
            component="type",
        ),
        torch.tensor(0.0),
    )


def test_deterministic_action_chooses_type_before_location():
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = _tiny_model(builder)
    type_logits = torch.full((1, 1, 6), -10.0)
    type_logits[..., 0] = 2.0
    type_logits[..., 4] = 1.0
    location_logits = torch.zeros((1, 1, 4, 576))
    location_logits[..., 0, 73] = 3.0
    mask = torch.zeros((1, 1, 2306), dtype=torch.bool)
    for slot in range(4):
        start = slot * 576
        mask[..., start : start + 100] = True
    mask[..., 2304] = True
    joint = model._joint_action_logits(type_logits, location_logits, mask)
    output = type(
        "Output",
        (),
        {
            "action_type_logits": type_logits,
            "location_logits": location_logits,
        },
    )()

    # Flat joint argmax incorrectly prefers no-op because the placement type's
    # probability is spread across 100 legal tiles. Hierarchical inference
    # first selects the higher-probability slot, then its best legal tile.
    assert int(joint.argmax(dim=-1).item()) == 2304
    action = model._deterministic_actions(output, mask)
    assert int(action.item()) == 73


def test_deterministic_action_masks_types_and_maps_special_actions():
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = _tiny_model(builder)
    type_logits = torch.full((1, 1, 6), -10.0)
    type_logits[..., 0] = 100.0  # Illegal placement slot must be ignored.
    type_logits[..., 5] = 2.0
    location_logits = torch.zeros((1, 1, 4, 576))
    mask = torch.zeros((1, 1, 2306), dtype=torch.bool)
    mask[..., 2304:] = True
    output = type(
        "Output",
        (),
        {
            "action_type_logits": type_logits,
            "location_logits": location_logits,
        },
    )()

    action = model._deterministic_actions(output, mask)
    assert int(action.item()) == 2305


def test_play_gate_deterministic_hierarchy_aggregates_hand_slots():
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = ClasherPolicy(
        replace(_tiny_model(builder).config, deterministic_hierarchy="play-gate"),
        builder.card_stat_features,
    )
    type_logits = torch.log(torch.tensor([[[0.16, 0.15, 0.15, 0.14, 0.40, 1e-9]]]))
    location_logits = torch.zeros((1, 1, 4, 576))
    location_logits[..., 0, 73] = 3.0
    mask = torch.zeros((1, 1, 2306), dtype=torch.bool)
    for slot in range(4):
        start = slot * 576
        mask[..., start : start + 100] = True
    mask[..., 2304] = True
    output = type(
        "Output",
        (),
        {
            "action_type_logits": type_logits,
            "location_logits": location_logits,
        },
    )()

    action = model._deterministic_actions(output, mask)

    assert int(action.item()) == 73


def test_unknown_deterministic_hierarchy_is_rejected():
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    with np.testing.assert_raises_regex(ValueError, "deterministic hierarchy"):
        ClasherPolicy(
            replace(_tiny_model(builder).config, deterministic_hierarchy="unknown"),
            builder.card_stat_features,
        )


def test_zero_initialized_repair_adapter_preserves_policy_exactly():
    env = SelfPlayBattleEnv(seed=13, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, repair_adapter_size=16),
        builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys
    assert all(name.startswith("repair_adapter.") for name in incompatible.missing_keys)

    observation = builder.build(env.battle, 0)
    mask = env.get_action_mask(0)[None, :]
    inputs = _stack_step_inputs(
        [observation],
        mask,
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    torch.testing.assert_close(actual.action_type_logits, expected.action_type_logits)
    torch.testing.assert_close(actual.location_logits, expected.location_logits)
    torch.testing.assert_close(actual.joint_logits, expected.joint_logits)
    torch.testing.assert_close(actual.values, expected.values)


def test_zero_initialized_action_type_adapter_preserves_policy_exactly():
    env = SelfPlayBattleEnv(seed=13, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, action_type_adapter_enabled=True),
        builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys
    assert all(
        name.startswith("action_type_adapter.") for name in incompatible.missing_keys
    )

    observation = builder.build(env.battle, 0)
    mask = env.get_action_mask(0)[None, :]
    inputs = _stack_step_inputs(
        [observation],
        mask,
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    torch.testing.assert_close(actual.action_type_logits, expected.action_type_logits)
    torch.testing.assert_close(actual.location_logits, expected.location_logits)
    torch.testing.assert_close(actual.joint_logits, expected.joint_logits)
    torch.testing.assert_close(actual.values, expected.values)


def test_action_type_adapter_cannot_change_location_logits():
    env = SelfPlayBattleEnv(seed=14, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, action_type_adapter_enabled=True),
        builder.card_stat_features,
    ).eval()
    adapted.load_state_dict(base.state_dict(), strict=False)
    assert adapted.action_type_adapter is not None
    with torch.no_grad():
        adapted.action_type_adapter.bias[0] = 2.0

    observation = builder.build(env.battle, 0)
    mask = env.get_action_mask(0)[None, :]
    inputs = _stack_step_inputs(
        [observation],
        mask,
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    torch.testing.assert_close(
        actual.action_type_logits[..., 0],
        expected.action_type_logits[..., 0] + 2.0,
    )
    torch.testing.assert_close(actual.location_logits, expected.location_logits)


def test_zero_safe_slot_choice_adapter_preserves_policy_bit_exactly():
    env = SelfPlayBattleEnv(seed=141, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, safe_slot_choice_adapter_enabled=True),
        builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys
    assert all(
        name.startswith("safe_slot_choice_adapter.")
        for name in incompatible.missing_keys
    )
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )

    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    assert torch.equal(actual.action_type_logits, expected.action_type_logits)
    assert torch.equal(actual.location_logits, expected.location_logits)
    assert torch.equal(actual.joint_logits, expected.joint_logits)
    assert torch.equal(actual.values, expected.values)


def test_safe_slot_choice_adapter_preserves_play_mass_and_deterministic_timing():
    env = SelfPlayBattleEnv(seed=142, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, safe_slot_choice_adapter_enabled=True),
        builder.card_stat_features,
    ).eval()
    adapted.load_state_dict(base.state_dict(), strict=False)
    assert adapted.safe_slot_choice_adapter is not None
    with torch.no_grad():
        adapted.safe_slot_choice_adapter.bias.copy_(torch.tensor([7.0, -4.0, 2.0, 5.0]))
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )

    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    assert torch.equal(
        actual.action_type_logits[..., 4:], expected.action_type_logits[..., 4:]
    )
    assert torch.equal(actual.location_logits, expected.location_logits)

    expected_play_probability = expected.joint_logits.exp()[..., : 4 * 18 * 32].sum(
        dim=-1
    )
    actual_play_probability = actual.joint_logits.exp()[..., : 4 * 18 * 32].sum(dim=-1)
    torch.testing.assert_close(
        actual_play_probability,
        expected_play_probability,
        atol=1e-6,
        rtol=0.0,
    )

    assert actual.deterministic_timing_logits is not None
    assert torch.equal(
        actual.deterministic_timing_logits,
        expected.action_type_logits,
    )
    expected_action = base._deterministic_actions(expected, inputs.action_mask)
    actual_action = adapted._deterministic_actions(actual, inputs.action_mask)
    expected_top_level = torch.where(expected_action < 4 * 18 * 32, 0, expected_action)
    actual_top_level = torch.where(actual_action < 4 * 18 * 32, 0, actual_action)
    assert torch.equal(actual_top_level, expected_top_level)


def test_semantic_slot_choice_adapter_preserves_play_mass_and_timing():
    env = SelfPlayBattleEnv(seed=143, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, semantic_slot_choice_adapter_enabled=True),
        builder.card_stat_features,
    ).eval()
    adapted.load_state_dict(base.state_dict(), strict=False)
    assert adapted.semantic_slot_choice_query is not None
    generator = torch.Generator().manual_seed(143)
    with torch.no_grad():
        adapted.semantic_slot_choice_query.weight.copy_(
            torch.randn(
                adapted.semantic_slot_choice_query.weight.shape,
                generator=generator,
            )
        )
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )

    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    assert not torch.equal(
        actual.action_type_logits[..., :4], expected.action_type_logits[..., :4]
    )
    assert torch.equal(
        actual.action_type_logits[..., 4:], expected.action_type_logits[..., 4:]
    )
    assert torch.equal(actual.location_logits, expected.location_logits)
    expected_play = expected.joint_logits.exp()[..., : 4 * 18 * 32].sum(dim=-1)
    actual_play = actual.joint_logits.exp()[..., : 4 * 18 * 32].sum(dim=-1)
    torch.testing.assert_close(actual_play, expected_play, atol=1e-6, rtol=0.0)
    assert actual.deterministic_timing_logits is not None
    assert torch.equal(actual.deterministic_timing_logits, expected.action_type_logits)


def test_semantic_slot_choice_replacement_preserves_play_mass_and_timing():
    env = SelfPlayBattleEnv(seed=149, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(
            base.config,
            semantic_slot_choice_adapter_enabled=True,
            semantic_slot_choice_replace_base=True,
        ),
        builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert incompatible.unexpected_keys == []
    assert incompatible.missing_keys == ["semantic_slot_choice_query.weight"]
    assert adapted.semantic_slot_choice_query is not None
    generator = torch.Generator().manual_seed(149)
    with torch.no_grad():
        adapted.semantic_slot_choice_query.weight.copy_(
            torch.randn(
                adapted.semantic_slot_choice_query.weight.shape,
                generator=generator,
            )
        )
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )

    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    assert not torch.equal(
        actual.action_type_logits[..., :4], expected.action_type_logits[..., :4]
    )
    assert torch.equal(
        actual.action_type_logits[..., 4:], expected.action_type_logits[..., 4:]
    )
    assert torch.equal(actual.location_logits, expected.location_logits)
    expected_play = expected.joint_logits.exp()[..., : 4 * 18 * 32].sum(dim=-1)
    actual_play = actual.joint_logits.exp()[..., : 4 * 18 * 32].sum(dim=-1)
    torch.testing.assert_close(actual_play, expected_play, atol=1e-6, rtol=0.0)
    assert actual.deterministic_timing_logits is not None
    assert torch.equal(actual.deterministic_timing_logits, expected.action_type_logits)


def test_zero_mechanics_slot_choice_adapter_preserves_policy_bit_exactly():
    env = SelfPlayBattleEnv(seed=150, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, mechanics_slot_choice_adapter_enabled=True),
        builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert incompatible.unexpected_keys == []
    assert set(incompatible.missing_keys) == {
        "mechanics_slot_card_stats",
        "mechanics_slot_choice_query.weight",
    }
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )

    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    assert torch.equal(actual.action_type_logits, expected.action_type_logits)
    assert torch.equal(actual.location_logits, expected.location_logits)
    assert torch.equal(actual.joint_logits, expected.joint_logits)
    assert torch.equal(actual.values, expected.values)


def test_mechanics_slot_choice_adapter_preserves_timing_and_geometry():
    env = SelfPlayBattleEnv(seed=151, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, mechanics_slot_choice_adapter_enabled=True),
        builder.card_stat_features,
    ).eval()
    adapted.load_state_dict(base.state_dict(), strict=False)
    assert adapted.mechanics_slot_choice_query is not None
    with torch.no_grad():
        adapted.mechanics_slot_choice_query.weight.copy_(
            torch.randn(
                adapted.mechanics_slot_choice_query.weight.shape,
                generator=torch.Generator().manual_seed(151),
            )
        )
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )

    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    assert not torch.equal(
        actual.action_type_logits[..., :4],
        expected.action_type_logits[..., :4],
    )
    assert torch.equal(
        actual.action_type_logits[..., 4:],
        expected.action_type_logits[..., 4:],
    )
    assert torch.equal(actual.location_logits, expected.location_logits)
    expected_play = expected.joint_logits.exp()[..., : 4 * 18 * 32].sum(dim=-1)
    actual_play = actual.joint_logits.exp()[..., : 4 * 18 * 32].sum(dim=-1)
    torch.testing.assert_close(actual_play, expected_play, atol=1e-6, rtol=0.0)
    assert actual.deterministic_timing_logits is not None
    assert torch.equal(actual.deterministic_timing_logits, expected.action_type_logits)


def test_equivariant_slot_choice_permutations_preserve_card_and_tile() -> None:
    torch.manual_seed(1511)
    env = SelfPlayBattleEnv(seed=1511, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    model = ClasherPolicy(
        replace(
            base.config,
            actor_current_hand_slot_invariant=True,
            mechanics_slot_choice_adapter_enabled=True,
            mechanics_slot_choice_replace_base=True,
            equivariant_slot_choice=True,
            equivariant_deterministic_timing_pool="max",
        ),
        builder.card_stat_features,
    ).eval()
    model.load_state_dict(base.state_dict(), strict=False)
    assert model.mechanics_slot_choice_query is not None
    with torch.no_grad():
        model.mechanics_slot_choice_query.weight.copy_(
            torch.randn(
                model.mechanics_slot_choice_query.weight.shape,
                generator=torch.Generator().manual_seed(1511),
            )
        )
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    action_mask = torch.zeros_like(inputs.action_mask)
    action_mask[..., : 4 * 18 * 32] = True
    action_mask[..., env.action_space.no_op_action] = True
    inputs = replace(inputs, action_mask=action_mask)
    order = torch.tensor([2, 0, 3, 1])
    hand_ids = inputs.hand_ids.clone()
    hand_ids[..., :4] = hand_ids[..., order]
    placement_mask = inputs.action_mask[..., : 4 * 18 * 32].reshape(1, 1, 4, 18 * 32)
    permuted_mask = torch.cat(
        [
            placement_mask[..., order, :].reshape(1, 1, -1),
            inputs.action_mask[..., 4 * 18 * 32 :],
        ],
        dim=-1,
    )
    permuted = replace(inputs, hand_ids=hand_ids, action_mask=permuted_mask)

    with torch.no_grad():
        captured_base_logits: list[torch.Tensor] = []
        hook = model.action_type_head.register_forward_hook(
            lambda _module, _inputs, output: captured_base_logits.append(
                output.detach()
            )
        )
        expected = model(inputs)
        hook.remove()
        actual = model(permuted)

    assert expected.deterministic_timing_logits is not None
    expected_play_timing = captured_base_logits[0][..., :4].amax(
        dim=-1,
        keepdim=True,
    )
    torch.testing.assert_close(
        expected.deterministic_timing_logits[..., :4],
        expected_play_timing.reshape(1, 1, 1).expand(1, 1, 4),
    )

    torch.testing.assert_close(
        actual.action_type_logits[..., :4],
        expected.action_type_logits[..., order],
        atol=2e-5,
        rtol=2e-5,
    )
    torch.testing.assert_close(
        actual.action_type_logits[..., 4:],
        expected.action_type_logits[..., 4:],
        atol=2e-5,
        rtol=2e-5,
    )
    torch.testing.assert_close(
        actual.location_logits,
        expected.location_logits[..., order, :],
        atol=2e-5,
        rtol=2e-5,
    )
    expected_action = int(model._deterministic_actions(expected, inputs.action_mask))
    actual_action = int(model._deterministic_actions(actual, permuted.action_mask))
    expected_slot, expected_tile = divmod(expected_action, 18 * 32)
    actual_slot, actual_tile = divmod(actual_action, 18 * 32)
    assert expected_slot < 4 and actual_slot < 4
    assert int(inputs.hand_ids[0, 0, expected_slot]) == int(
        permuted.hand_ids[0, 0, actual_slot]
    )
    assert actual_tile == expected_tile


def test_hierarchical_mode_gate_composes_normalized_play_card_tile_policy() -> None:
    torch.manual_seed(1512)
    env = SelfPlayBattleEnv(seed=1512, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    model = ClasherPolicy(
        replace(
            _tiny_model(builder).config,
            hierarchical_mode_gate_enabled=True,
        ),
        builder.card_stat_features,
    ).eval()
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )

    with torch.no_grad():
        output = model(inputs)

    probabilities = output.distribution().probs
    torch.testing.assert_close(
        probabilities.sum(dim=-1),
        torch.ones((1, 1)),
        atol=1e-6,
        rtol=0.0,
    )
    placement = probabilities[..., : 4 * 18 * 32].reshape(1, 1, 4, 18 * 32)
    slot_mass = placement.sum(dim=-1)
    special_mass = probabilities[..., 4 * 18 * 32 :]
    type_mass = torch.cat([slot_mass, special_mass], dim=-1)
    expected_type_mass = output.action_type_logits.exp()
    expected_type_mass = expected_type_mass * torch.cat(
        [
            inputs.action_mask[..., : 4 * 18 * 32]
            .reshape(1, 1, 4, 18 * 32)
            .any(dim=-1),
            inputs.action_mask[..., 4 * 18 * 32 :],
        ],
        dim=-1,
    )
    torch.testing.assert_close(type_mass, expected_type_mass, atol=1e-6, rtol=0.0)
    assert output.deterministic_timing_logits is not None


@pytest.mark.parametrize(
    "updates",
    [
        {"equivariant_slot_choice": True},
        {
            "equivariant_slot_choice": True,
            "actor_current_hand_slot_invariant": True,
        },
    ],
)
def test_equivariant_slot_choice_rejects_incomplete_configuration(
    updates: dict[str, bool],
) -> None:
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=8)
    with pytest.raises(ValueError, match="equivariant slot choice"):
        ClasherPolicy(
            replace(_tiny_model(builder).config, **updates),
            builder.card_stat_features,
        )


def test_mechanics_slot_scores_do_not_use_card_identity() -> None:
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=8)
    model = ClasherPolicy(
        replace(
            _tiny_model(builder).config,
            mechanics_slot_choice_adapter_enabled=True,
        ),
        builder.card_stat_features,
    ).eval()
    assert model.mechanics_slot_card_stats is not None
    assert model.mechanics_slot_choice_query is not None
    with torch.no_grad():
        model.mechanics_slot_card_stats[3].copy_(model.mechanics_slot_card_stats[2])
        model.mechanics_slot_choice_query.weight.copy_(
            torch.randn(
                model.mechanics_slot_choice_query.weight.shape,
                generator=torch.Generator().manual_seed(152),
            )
        )
    repair_features = torch.randn(
        (2, model.config.d_model + model.config.memory_size),
        generator=torch.Generator().manual_seed(153),
    )
    hand_ids = torch.tensor([[2, 3, 2, 3], [3, 2, 3, 2]])

    scores = model._mechanics_slot_choice_scores(repair_features, hand_ids)

    torch.testing.assert_close(scores[:, 0], scores[:, 1])
    torch.testing.assert_close(scores[:, 2], scores[:, 3])


def test_mechanics_slot_adapter_reproduces_configured_logit_blend() -> None:
    env = SelfPlayBattleEnv(seed=154, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(
            base.config,
            mechanics_slot_choice_adapter_enabled=True,
            mechanics_slot_choice_base_scale=0.7,
        ),
        builder.card_stat_features,
    ).eval()
    adapted.load_state_dict(base.state_dict(), strict=False)
    assert adapted.mechanics_slot_choice_query is not None
    with torch.no_grad():
        adapted.mechanics_slot_choice_query.weight.copy_(
            0.3
            * torch.randn(
                adapted.mechanics_slot_choice_query.weight.shape,
                generator=torch.Generator().manual_seed(154),
            )
        )
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )

    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)
    assert expected.repair_features is not None
    mechanics = adapted._mechanics_slot_choice_scores(
        expected.repair_features.reshape(-1, expected.repair_features.shape[-1]),
        inputs.hand_ids.reshape(-1, inputs.hand_ids.shape[-1])[:, :4],
    ).reshape_as(expected.action_type_logits[..., :4])
    raw = 0.7 * expected.action_type_logits[..., :4] + mechanics
    legal = (
        inputs.action_mask[..., : 4 * 18 * 32]
        .reshape(*inputs.action_mask.shape[:-1], 4, 18 * 32)
        .any(dim=-1)
    )
    masked_base = expected.action_type_logits[..., :4].masked_fill(~legal, -torch.inf)
    masked_raw = raw.masked_fill(~legal, -torch.inf)
    shift = torch.logsumexp(masked_raw, dim=-1, keepdim=True) - torch.logsumexp(
        masked_base,
        dim=-1,
        keepdim=True,
    )

    torch.testing.assert_close(actual.action_type_logits[..., :4], raw - shift)
    assert torch.equal(
        actual.action_type_logits[..., 4:],
        expected.action_type_logits[..., 4:],
    )


def test_zero_initialized_robust_action_adapter_preserves_policy_exactly():
    env = SelfPlayBattleEnv(seed=15, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, robust_action_type_adapter_size=16),
        builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys
    assert all(
        name == "robust_action_card_stats"
        or name.startswith("robust_action_type_adapter.")
        for name in incompatible.missing_keys
    )

    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    torch.testing.assert_close(actual.action_type_logits, expected.action_type_logits)
    torch.testing.assert_close(actual.location_logits, expected.location_logits)
    torch.testing.assert_close(actual.joint_logits, expected.joint_logits)
    torch.testing.assert_close(actual.values, expected.values)


def test_robust_action_adapter_cannot_change_location_logits():
    env = SelfPlayBattleEnv(seed=16, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, robust_action_type_adapter_size=16),
        builder.card_stat_features,
    ).eval()
    adapted.load_state_dict(base.state_dict(), strict=False)
    assert adapted.robust_action_type_adapter is not None
    output = adapted.robust_action_type_adapter[-1]
    assert isinstance(output, nn.Linear)
    with torch.no_grad():
        output.bias[0] = 2.0

    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    torch.testing.assert_close(
        actual.action_type_logits[..., 0],
        expected.action_type_logits[..., 0] + 2.0,
    )
    torch.testing.assert_close(actual.location_logits, expected.location_logits)


def test_robust_action_features_exclude_unreliable_visual_fields():
    env = SelfPlayBattleEnv(seed=17, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    model = ClasherPolicy(
        replace(_tiny_model(builder).config, robust_action_type_adapter_size=16),
        builder.card_stat_features,
    ).eval()
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )

    # Turn one visible tower row into a synthetic troop row so the positional
    # sensitivity assertion does not depend on a particular randomized deck.
    reliable_entities = inputs.entity_features.clone()
    first_valid = int(inputs.entity_mask[0, 0].nonzero()[0].item())
    reliable_entities[0, 0, first_valid, 4:9] = 0.0
    reliable_entities[0, 0, first_valid, 4] = 1.0
    inputs = replace(inputs, entity_features=reliable_entities)

    unreliable_entities = inputs.entity_features.clone()
    unreliable_entities[..., 9:32] = torch.rand_like(unreliable_entities[..., 9:32])
    unreliable_globals = inputs.global_features.clone()
    unreliable_globals[..., 6:] = torch.rand_like(unreliable_globals[..., 6:])
    unreliable = replace(
        inputs,
        entity_features=unreliable_entities,
        global_features=unreliable_globals,
    )
    with torch.no_grad():
        expected = model._robust_action_features(inputs)
        actual = model._robust_action_features(unreliable)
    torch.testing.assert_close(actual, expected)

    changed_elixir = inputs.global_features.clone()
    changed_elixir[..., 5] = 1.0 - changed_elixir[..., 5]
    changed_position = inputs.entity_features.clone()
    changed_position[0, 0, first_valid, 0] = torch.where(
        changed_position[0, 0, first_valid, 0] > 0.5,
        torch.tensor(0.123),
        torch.tensor(0.877),
    )
    with torch.no_grad():
        elixir_features = model._robust_action_features(
            replace(inputs, global_features=changed_elixir)
        )
        position_features = model._robust_action_features(
            replace(inputs, entity_features=changed_position)
        )
    assert not torch.equal(elixir_features, expected)
    assert not torch.equal(position_features, expected)


def test_semantic_v3_upgrade_preserves_v1_policy_exactly():
    env = SelfPlayBattleEnv(seed=17, max_ticks=128)
    env.reset()
    legacy_builder = StructuredObservationBuilder(
        decks_path="decks.json",
        max_entities=128,
    )
    semantic_builder = StructuredObservationBuilder(
        decks_path="decks.json",
        max_entities=128,
        token_names=legacy_builder.token_names,
        card_semantics_version=3,
    )
    base = _tiny_model(legacy_builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, card_semantics_version=3),
        semantic_builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys
    assert all(
        name.startswith(
            (
                "actor_encoder.semantic_card_",
                "critic_encoder.semantic_card_",
            )
        )
        for name in incompatible.missing_keys
    )

    observation = legacy_builder.build(env.battle, 0)
    mask = env.get_action_mask(0)[None, :]
    inputs = _stack_step_inputs(
        [observation],
        mask,
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    torch.testing.assert_close(actual.action_type_logits, expected.action_type_logits)
    torch.testing.assert_close(actual.location_logits, expected.location_logits)
    torch.testing.assert_close(actual.joint_logits, expected.joint_logits)
    torch.testing.assert_close(actual.values, expected.values)


def test_card_placement_prior_is_zero_preserving_and_location_only():
    env = SelfPlayBattleEnv(seed=131, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, placement_prior_enabled=True),
        builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys == ["placement_prior.weight"]

    observation = builder.build(env.battle, 0)
    hand_ids = np.zeros_like(observation.hand_ids)
    knight_id = builder.token_id("Knight")
    hand_ids[0] = knight_id
    observation = replace(observation, hand_ids=hand_ids)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        zero_prior = adapted(inputs)
        assert adapted.placement_prior is not None
        adapted.placement_prior.weight[knight_id, 7] = 1.5
        changed = adapted(inputs)

    torch.testing.assert_close(zero_prior.joint_logits, expected.joint_logits)
    torch.testing.assert_close(
        changed.action_type_logits,
        expected.action_type_logits,
    )
    delta = changed.location_logits - expected.location_logits
    torch.testing.assert_close(delta[0, 0, 0, 7], torch.tensor(1.5))
    assert torch.count_nonzero(delta).item() == 1
    torch.testing.assert_close(changed.values, expected.values)


def test_zero_initialized_repair_stage_preserves_policy_exactly():
    env = SelfPlayBattleEnv(seed=14, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(base.config, repair_stage_sizes=(16,)),
        builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys
    assert all(
        name.startswith("repair_stages.0.") for name in incompatible.missing_keys
    )

    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)

    torch.testing.assert_close(actual.action_type_logits, expected.action_type_logits)
    torch.testing.assert_close(actual.location_logits, expected.location_logits)
    torch.testing.assert_close(actual.joint_logits, expected.joint_logits)
    torch.testing.assert_close(actual.values, expected.values)


def test_repair_stages_support_distinct_prototype_thresholds():
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(
            base.config,
            repair_stage_sizes=(8, 8),
            repair_stage_prototype_counts=(1, 1),
            repair_stage_prototype_thresholds=(0.99999, 0.999),
        ),
        builder.card_stat_features,
    ).eval()

    first = adapted.repair_stage_prototype_adapters["0"]
    second = adapted.repair_stage_prototype_adapters["1"]
    torch.testing.assert_close(
        first._thresholds,
        torch.full_like(first._thresholds, 0.99999),
    )
    torch.testing.assert_close(
        second._thresholds,
        torch.full_like(second._thresholds, 0.999),
    )
    assert all(
        torch.count_nonzero(parameter) == 0
        for stage in adapted.repair_stages
        for parameter in stage[-1].parameters()
    )
    assert torch.count_nonzero(first.deltas) == 0
    assert torch.count_nonzero(second.deltas) == 0


def test_broad_repair_stage_yields_to_an_active_prior_stage():
    env = SelfPlayBattleEnv(seed=16, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(
            base.config,
            repair_stage_sizes=(8, 8),
            repair_stage_prototype_counts=(1, 1),
            repair_stage_prototype_thresholds=(0.99999, 0.999),
            repair_stage_yield_to_prior=(False, True),
        ),
        builder.card_stat_features,
    ).eval()
    adapted.load_state_dict(base.state_dict(), strict=False)
    inputs = _stack_step_inputs(
        [builder.build(env.battle, 0)],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        zero_output = adapted(inputs)
    assert zero_output.repair_features is not None
    repair_features = zero_output.repair_features[0]
    first = adapted.repair_stage_prototype_adapters["0"]
    second = adapted.repair_stage_prototype_adapters["1"]
    first.set_prototypes(repair_features)
    second.set_prototypes(repair_features)
    with torch.no_grad():
        first.deltas[0, 0] = 3.0
        second.deltas[0, 0] = 5.0
        actual = adapted(inputs)

    torch.testing.assert_close(
        actual.action_type_logits[..., 0],
        expected.action_type_logits[..., 0] + 3.0,
    )


def test_stage_guard_prototype_suppresses_broad_suffix_prototypes():
    hard_adapter = PrototypeRepairAdapter(
        input_size=2,
        output_size=1,
        prototype_count=2,
        threshold=0.999,
        frozen_prefix_count=1,
        frozen_prefix_threshold=0.99999,
        guard_count=1,
        guard_threshold=0.99999,
        hard_guard=True,
    )
    cosine = 0.999995
    hard_adapter.set_prototypes(
        torch.tensor(
            [[cosine, math.sqrt(1.0 - cosine**2)], [1.0, 0.0]],
            dtype=torch.float32,
        )
    )
    hard_weights = hard_adapter.activation_weights(torch.tensor([[1.0, 0.0]]))
    assert 0.0 < hard_weights[0, 0] < 1.0
    assert hard_weights[0, 1] == 0.0

    env = SelfPlayBattleEnv(seed=18, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(
            base.config,
            repair_stage_sizes=(8,),
            repair_stage_prototype_counts=(2,),
            repair_stage_prototype_thresholds=(0.999,),
            repair_stage_prototype_guard_counts=(1,),
            repair_stage_prototype_guard_thresholds=(0.99999,),
            repair_stage_prototype_hard_guards=(True,),
        ),
        builder.card_stat_features,
    ).eval()
    adapted.load_state_dict(base.state_dict(), strict=False)
    inputs = _stack_step_inputs(
        [builder.build(env.battle, 0)],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        zero_output = adapted(inputs)
    assert zero_output.repair_features is not None
    repair_features = zero_output.repair_features[0]
    adapter = adapted.repair_stage_prototype_adapters["0"]
    adapter.set_prototypes(torch.cat([repair_features, repair_features], dim=0))
    with torch.no_grad():
        adapter.deltas[1, 0] = 5.0
        guarded = adapted(inputs)
        adapter.prototypes[0].copy_(-repair_features[0])
        unguarded = adapted(inputs)

    torch.testing.assert_close(guarded.joint_logits, expected.joint_logits)
    torch.testing.assert_close(
        unguarded.action_type_logits[..., 0],
        expected.action_type_logits[..., 0] + 5.0,
    )


def test_repair_stage_guard_suppresses_only_its_own_dense_residual():
    env = SelfPlayBattleEnv(seed=15, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(
            base.config,
            repair_adapter_size=8,
            repair_stage_sizes=(8,),
            repair_stage_prototype_counts=(1,),
        ),
        builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys

    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        zero_output = adapted(inputs)
    assert zero_output.repair_features is not None
    stage_prototypes = adapted.repair_stage_prototype_adapters["0"]
    stage_prototypes.set_prototypes(zero_output.repair_features[0])
    with torch.no_grad():
        assert adapted.repair_adapter is not None
        base_final = adapted.repair_adapter[-1]
        stage_final = adapted.repair_stages[0][-1]
        assert isinstance(base_final, nn.Linear)
        assert isinstance(stage_final, nn.Linear)
        base_final.bias[0] = 4.0
        stage_final.bias[0] = 2.0
        stage_prototypes.deltas[0, 0] = 3.0
        changed = adapted(inputs)
    torch.testing.assert_close(
        changed.action_type_logits[..., 0],
        expected.action_type_logits[..., 0] + 7.0,
    )

    far_inputs = replace(inputs, global_features=-inputs.global_features)
    with torch.no_grad():
        far_expected = base(far_inputs)
        far_changed = adapted(far_inputs)
    torch.testing.assert_close(
        far_changed.action_type_logits[..., 0],
        far_expected.action_type_logits[..., 0] + 6.0,
    )


def test_prototype_repair_adapter_is_exactly_local_and_zero_initialized():
    env = SelfPlayBattleEnv(seed=17, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(
            base.config,
            repair_prototype_count=1,
            repair_prototype_threshold=0.999,
        ),
        builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys
    assert all(
        name.startswith("prototype_repair_adapter.")
        for name in incompatible.missing_keys
    )

    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        zero_output = adapted(inputs)
    torch.testing.assert_close(zero_output.joint_logits, expected.joint_logits)
    assert zero_output.repair_features is not None
    assert adapted.prototype_repair_adapter is not None
    adapted.prototype_repair_adapter.set_prototypes(zero_output.repair_features[0])
    with torch.no_grad():
        adapted.prototype_repair_adapter.deltas[0, 0] = 1.0
        changed = adapted(inputs)
    torch.testing.assert_close(
        changed.action_type_logits[..., 0],
        expected.action_type_logits[..., 0] + 1.0,
    )
    far_weights = adapted.prototype_repair_adapter.activation_weights(
        -zero_output.repair_features[0]
    )
    torch.testing.assert_close(far_weights, torch.zeros_like(far_weights))


def test_prototype_repair_similarity_can_use_actor_context_only():
    adapter = PrototypeRepairAdapter(
        input_size=4,
        output_size=2,
        prototype_count=1,
        threshold=0.999,
        feature_size=2,
    )
    adapter.set_prototypes(torch.tensor([[1.0, 0.0, 1.0, 0.0]]))

    same_actor_opposite_memory = torch.tensor([[1.0, 0.0, -1.0, 0.0]])
    weights = adapter.activation_weights(same_actor_opposite_memory)

    torch.testing.assert_close(weights, torch.ones_like(weights))


def test_prototype_repair_can_keep_a_frozen_prefix_strict():
    adapter = PrototypeRepairAdapter(
        input_size=2,
        output_size=2,
        prototype_count=2,
        threshold=0.9999,
        frozen_prefix_count=1,
        frozen_prefix_threshold=0.99999,
    )
    adapter.set_prototypes(torch.tensor([[1.0, 0.0], [1.0, 0.0]]))
    similarity = 0.99995
    nearby = torch.tensor([[similarity, (1.0 - similarity * similarity) ** 0.5]])

    weights = adapter.activation_weights(nearby)

    torch.testing.assert_close(weights[:, 0], torch.zeros(1))
    torch.testing.assert_close(
        weights[:, 1], torch.full((1,), 0.25), atol=1e-4, rtol=1e-4
    )


def test_prototype_repair_guard_suppresses_only_wide_suffix():
    adapter = PrototypeRepairAdapter(
        input_size=2,
        output_size=1,
        prototype_count=3,
        threshold=0.98,
        frozen_prefix_count=2,
        frozen_prefix_threshold=0.99999,
        guard_count=1,
        guard_threshold=0.99999,
    )
    adapter.set_prototypes(torch.tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]))
    with torch.no_grad():
        adapter.deltas.copy_(torch.tensor([[0.0], [2.0], [3.0]]))

    weights = adapter.activation_weights(torch.tensor([[1.0, 0.0]]))

    torch.testing.assert_close(weights, torch.tensor([[1.0, 0.0, 0.0]]))
    torch.testing.assert_close(adapter(torch.tensor([[1.0, 0.0]])), torch.zeros(1, 1))


def test_prototype_repair_linear_gate_controls_wide_suffix():
    adapter = PrototypeRepairAdapter(
        input_size=2,
        output_size=1,
        prototype_count=2,
        threshold=0.98,
        frozen_prefix_count=1,
        frozen_prefix_threshold=0.99999,
        linear_gate_count=1,
    )
    adapter.set_prototypes(torch.tensor([[0.0, 1.0], [1.0, 0.0]]))
    with torch.no_grad():
        adapter.deltas.copy_(torch.tensor([[0.0], [3.0]]))
    inputs = torch.tensor([[1.0, 0.0]])

    adapter.set_linear_gates(torch.tensor([[1.0, 0.0]]), torch.tensor([-2.0]))
    torch.testing.assert_close(adapter(inputs), torch.zeros(1, 1))

    adapter.set_linear_gates(torch.tensor([[1.0, 0.0]]), torch.tensor([0.0]))
    torch.testing.assert_close(adapter(inputs), torch.full((1, 1), 3.0))


def test_prototype_repair_linear_gates_route_suffix_rows_independently():
    adapter = PrototypeRepairAdapter(
        input_size=2,
        output_size=1,
        prototype_count=3,
        threshold=0.98,
        frozen_prefix_count=1,
        frozen_prefix_threshold=0.99999,
        linear_gate_count=2,
    )
    adapter.set_prototypes(torch.tensor([[0.0, 1.0], [1.0, 0.0], [1.0, 0.0]]))
    with torch.no_grad():
        adapter.deltas.copy_(torch.tensor([[0.0], [2.0], [5.0]]))
    inputs = torch.tensor([[1.0, 0.0]])
    weights = torch.tensor([[1.0, 0.0], [1.0, 0.0]])

    adapter.set_linear_gates(weights, torch.tensor([0.0, -2.0]))
    torch.testing.assert_close(adapter(inputs), torch.full((1, 1), 2.0))

    adapter.set_linear_gates(weights, torch.tensor([-2.0, 0.0]))
    torch.testing.assert_close(adapter(inputs), torch.full((1, 1), 5.0))


def test_prototype_repair_suppresses_dense_residual_in_verified_neighborhood():
    env = SelfPlayBattleEnv(seed=19, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    base = _tiny_model(builder).eval()
    adapted = ClasherPolicy(
        replace(
            base.config,
            repair_adapter_size=8,
            repair_prototype_count=1,
            repair_prototype_threshold=0.999,
        ),
        builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys

    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        zero_output = adapted(inputs)
    torch.testing.assert_close(zero_output.joint_logits, expected.joint_logits)
    assert zero_output.repair_features is not None
    assert adapted.repair_adapter is not None
    assert adapted.prototype_repair_adapter is not None
    adapted.prototype_repair_adapter.set_prototypes(zero_output.repair_features[0])
    with torch.no_grad():
        dense_final = adapted.repair_adapter[-1]
        assert isinstance(dense_final, nn.Linear)
        dense_final.bias[0] = 2.0
        adapted.prototype_repair_adapter.deltas[0, 0] = 3.0
        changed = adapted(inputs)
    torch.testing.assert_close(
        changed.action_type_logits[..., 0],
        expected.action_type_logits[..., 0] + 3.0,
    )

    far_inputs = replace(inputs, global_features=-inputs.global_features)
    with torch.no_grad():
        far_expected = base(far_inputs)
        far_changed = adapted(far_inputs)
    torch.testing.assert_close(
        far_changed.action_type_logits[..., 0],
        far_expected.action_type_logits[..., 0] + 2.0,
    )


def test_recurrent_state_resets_inside_a_sequence():
    env = SelfPlayBattleEnv(seed=11, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    env._structured_obs_builder = builder
    model = _tiny_model(builder).eval()
    observation = builder.build(env.battle, 0)
    mask = env.get_action_mask(0)[None, :]
    single = _stack_step_inputs(
        [observation],
        mask,
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    doubled = PolicyInputs(
        **{
            name: torch.cat([getattr(single, name), getattr(single, name)], dim=1)
            for name in (
                "entity_ids",
                "entity_features",
                "entity_mask",
                "hand_ids",
                "global_features",
                "action_mask",
                "previous_actions",
                "previous_rewards",
                "episode_starts",
                "critic_entity_ids",
                "critic_entity_features",
                "critic_entity_mask",
                "critic_card_ids",
                "critic_global_features",
            )
        }
    )
    with torch.no_grad():
        standalone = model(single).next_state
        sequence = model(doubled).next_state
    torch.testing.assert_close(sequence[0], standalone[0])
    torch.testing.assert_close(sequence[1], standalone[1])


def test_recurrent_rollout_and_ppo_update_smoke():
    env = SelfPlayBattleEnv(seed=17, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    env._structured_obs_builder = builder
    model = _tiny_model(builder)
    anchor_model = deepcopy(model).eval()
    anchor_model.requires_grad_(False)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    state = model.initial_state(2)
    previous_actions = np.full((2,), env.action_space.no_op_action, dtype=np.int64)
    previous_rewards = np.zeros((2,), dtype=np.float32)
    starts = np.ones((2,), dtype=np.bool_)

    rollout, _, _, _, _ = collect_rollout(
        envs=[env],
        builder=builder,
        model=model,
        device=torch.device("cpu"),
        rollout_steps=2,
        recurrent_state=state,
        previous_actions=previous_actions,
        previous_rewards=previous_rewards,
        episode_starts=starts,
        quiet_engine=True,
    )
    advantages, returns = compute_gae(rollout, gamma=0.995, gae_lambda=0.95)

    class FakeRehearsal:
        calls = 0

        def loss(self, rehearsal_model, *, device, batch_sequences):
            self.calls += 1
            assert device == torch.device("cpu")
            assert batch_sequences == 1
            return next(rehearsal_model.parameters()).square().mean()

    rehearsal = FakeRehearsal()

    class FakeAnchorRehearsal:
        calls = 0

        def anchor_policy_kl(
            self,
            rehearsal_model,
            frozen_anchor_model,
            *,
            device,
            batch_sequences,
        ):
            self.calls += 1
            assert device == torch.device("cpu")
            assert batch_sequences == 2
            current = next(rehearsal_model.parameters())
            frozen = next(frozen_anchor_model.parameters())
            return (current - frozen).square().mean()

    anchor_rehearsal = FakeAnchorRehearsal()
    stats = ppo_update(
        model=model,
        optimizer=optimizer,
        rollout=rollout,
        advantages=advantages,
        returns=returns,
        device=torch.device("cpu"),
        epochs=1,
        sequence_batch_size=1,
        clip_ratio=0.2,
        value_coef=0.5,
        entropy_coef=0.01,
        hand_aux_coef=0.02,
        elixir_aux_coef=0.05,
        target_kl=0.0,
        anchor_model=anchor_model,
        anchor_policy_kl_coef=0.1,
        rehearsal=rehearsal,
        rehearsal_coef=0.01,
        anchor_rehearsal=anchor_rehearsal,
        anchor_rehearsal_coef=0.1,
        anchor_rehearsal_batch_sequences=2,
    )
    assert rollout.transitions == 4
    assert np.isfinite(advantages).all()
    assert all(np.isfinite(value) for value in stats.values())
    assert stats["anchor_policy_kl"] >= 0.0
    assert stats["rehearsal_weighted_loss"] >= 0.0
    assert stats["anchor_rehearsal_kl"] >= 0.0
    assert rehearsal.calls == stats["optimizer_steps"]
    assert anchor_rehearsal.calls == stats["optimizer_steps"]
    assert all(parameter.grad is None for parameter in anchor_model.parameters())

    combined = concatenate_rollouts([rollout, rollout])
    assert combined.num_sequences == 2 * rollout.num_sequences
    assert combined.transitions == 2 * rollout.transitions
    assert combined.episodes_finished == 2 * rollout.episodes_finished
    np.testing.assert_array_equal(combined.actions[:2], rollout.actions)
    np.testing.assert_array_equal(combined.actions[2:], rollout.actions)


def test_causal_rollout_never_feeds_privileged_previous_reward() -> None:
    env = SelfPlayBattleEnv(seed=1701, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    env._structured_obs_builder = builder
    baseline = _tiny_model(builder)
    model = ClasherPolicy(
        replace(
            baseline.config,
            actor_observation_domain="causal-vision-v1",
            public_observation_confidence=True,
        ),
        builder.card_stat_features,
    )
    no_op = env.action_space.no_op_action

    rollout, _, _, previous_rewards, _ = collect_rollout(
        envs=[env],
        builder=builder,
        model=model,
        device=torch.device("cpu"),
        rollout_steps=2,
        recurrent_state=model.initial_state(2),
        previous_actions=np.full((2,), no_op, dtype=np.int64),
        previous_rewards=np.full((2,), 7.0, dtype=np.float32),
        episode_starts=np.ones((2,), dtype=np.bool_),
        quiet_engine=True,
    )

    assert np.count_nonzero(rollout.previous_rewards) == 0
    assert np.count_nonzero(previous_rewards) == 0

    observations = [
        env.get_structured_observation(
            player_id, actor_observation_domain="causal-vision-v1"
        )
        for player_id in (0, 1)
    ]
    masks = np.stack(
        [
            env.get_action_mask(
                player_id,
                actor_observation_domain="causal-vision-v1",
                structured_observation=observation,
            )
            for player_id, observation in enumerate(observations)
        ]
    )
    inputs = _stack_step_inputs(
        observations,
        masks,
        np.full((2,), no_op, dtype=np.int64),
        np.zeros((2,), dtype=np.float32),
        np.ones((2,), dtype=np.bool_),
        torch.device("cpu"),
        public_observation_confidence=True,
    )
    with torch.no_grad():
        zero_reward = model(inputs, model.initial_state(2))
        fake_reward = model(
            replace(
                inputs, previous_rewards=torch.full_like(inputs.previous_rewards, 9.0)
            ),
            model.initial_state(2),
        )
    torch.testing.assert_close(fake_reward.joint_logits, zero_reward.joint_logits)
    torch.testing.assert_close(fake_reward.next_state[0], zero_reward.next_state[0])


def test_ppo_conditional_slot_entropy_only_changes_loss_when_enabled():
    env = SelfPlayBattleEnv(seed=117, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    env._structured_obs_builder = builder
    baseline_model = _tiny_model(builder)
    explored_model = deepcopy(baseline_model)
    state = baseline_model.initial_state(2)
    rollout, _, _, _, _ = collect_rollout(
        envs=[env],
        builder=builder,
        model=baseline_model,
        device=torch.device("cpu"),
        rollout_steps=1,
        recurrent_state=state,
        previous_actions=np.full((2,), env.action_space.no_op_action, dtype=np.int64),
        previous_rewards=np.zeros((2,), dtype=np.float32),
        episode_starts=np.ones((2,), dtype=np.bool_),
        quiet_engine=True,
    )
    advantages, returns = compute_gae(rollout, gamma=0.995, gae_lambda=0.95)
    kwargs = {
        "rollout": rollout,
        "advantages": advantages,
        "returns": returns,
        "device": torch.device("cpu"),
        "epochs": 1,
        "sequence_batch_size": rollout.num_sequences,
        "clip_ratio": 0.2,
        "value_coef": 0.5,
        "entropy_coef": 0.0,
        "hand_aux_coef": 0.02,
        "elixir_aux_coef": 0.05,
        "target_kl": 0.0,
    }

    baseline = ppo_update(
        model=baseline_model,
        optimizer=torch.optim.SGD(baseline_model.parameters(), lr=0.0),
        conditional_slot_entropy_coef=0.0,
        **kwargs,
    )
    explored = ppo_update(
        model=explored_model,
        optimizer=torch.optim.SGD(explored_model.parameters(), lr=0.0),
        conditional_slot_entropy_coef=0.25,
        **kwargs,
    )

    assert explored["conditional_slot_entropy"] > 0.0
    assert baseline["conditional_slot_entropy"] == pytest.approx(
        explored["conditional_slot_entropy"]
    )
    assert baseline["loss"] - explored["loss"] == pytest.approx(
        0.25 * explored["conditional_slot_entropy"], abs=1e-6
    )


def test_ppo_update_rejects_nonfinite_loss_before_mutating_parameters():
    env = SelfPlayBattleEnv(seed=18, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    env._structured_obs_builder = builder
    model = _tiny_model(builder)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    state = model.initial_state(2)
    previous_actions = np.full((2,), env.action_space.no_op_action, dtype=np.int64)
    previous_rewards = np.zeros((2,), dtype=np.float32)
    starts = np.ones((2,), dtype=np.bool_)
    rollout, _, _, _, _ = collect_rollout(
        envs=[env],
        builder=builder,
        model=model,
        device=torch.device("cpu"),
        rollout_steps=1,
        recurrent_state=state,
        previous_actions=previous_actions,
        previous_rewards=previous_rewards,
        episode_starts=starts,
        quiet_engine=True,
    )
    advantages, returns = compute_gae(rollout, gamma=0.995, gae_lambda=0.95)
    before = tuple(parameter.detach().clone() for parameter in model.parameters())

    class NonfiniteRehearsal:
        def loss(self, rehearsal_model, *, device, batch_sequences):
            del device, batch_sequences
            parameter = next(rehearsal_model.parameters())
            return parameter.sum() * torch.tensor(float("nan"))

    with pytest.raises(FloatingPointError, match="non-finite PPO loss"):
        ppo_update(
            model=model,
            optimizer=optimizer,
            rollout=rollout,
            advantages=advantages,
            returns=returns,
            device=torch.device("cpu"),
            epochs=1,
            sequence_batch_size=1,
            clip_ratio=0.2,
            value_coef=0.5,
            entropy_coef=0.01,
            hand_aux_coef=0.02,
            elixir_aux_coef=0.05,
            target_kl=0.0,
            rehearsal=NonfiniteRehearsal(),
            rehearsal_coef=1.0,
        )

    for parameter, original in zip(model.parameters(), before, strict=True):
        torch.testing.assert_close(parameter, original)


def test_random_opponent_rollout_only_trains_balanced_learner_seats():
    envs = [SelfPlayBattleEnv(seed=31 + index, max_ticks=128) for index in range(2)]
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    for env in envs:
        env._structured_obs_builder = builder
        env.reset()
    model = _tiny_model(builder)
    state = model.initial_state(2)
    no_op = envs[0].action_space.no_op_action

    rollout, next_state, previous_actions, previous_rewards, starts, *_ = (
        collect_rollout_stationary_opponents(
            envs=envs,
            learner_players=(0, 1),
            builder=builder,
            model=model,
            device=torch.device("cpu"),
            rollout_steps=2,
            recurrent_state=state,
            previous_actions=np.full((2,), no_op, dtype=np.int64),
            previous_rewards=np.zeros((2,), dtype=np.float32),
            episode_starts=np.ones((2,), dtype=np.bool_),
            opponent_model=None,
            opponent_recurrent_state=None,
            opponent_previous_actions=np.full((2,), no_op, dtype=np.int64),
            opponent_previous_rewards=np.zeros((2,), dtype=np.float32),
            opponent_episode_starts=np.ones((2,), dtype=np.bool_),
            quiet_engine=True,
        )
    )

    assert rollout.num_sequences == 2
    assert rollout.transitions == 4
    assert rollout.actions.shape == (2, 2)
    assert rollout.bootstrap_values.shape == (2,)
    assert next_state[0].shape == (2, model.config.memory_size)
    assert previous_actions.shape == previous_rewards.shape == starts.shape == (2,)
    assert np.all(
        np.take_along_axis(
            rollout.action_masks,
            rollout.actions[..., None],
            axis=-1,
        )
    )


def test_mixed_defense_scenario_only_suppresses_its_stationary_opponent():
    envs = [
        SelfPlayBattleEnv(
            seed=67,
            max_ticks=512,
            defense_scenario_probability=1.0,
            defense_scenario_horizon_ticks=240,
        ),
        SelfPlayBattleEnv(seed=68, max_ticks=512),
    ]
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    recorded_actions: list[dict[int, int]] = []
    for env in envs:
        env._structured_obs_builder = builder
        env.reset()
        original_step = env.step

        def recording_step(actions, *, pre_action_masks=None, _step=original_step):
            recorded_actions.append(dict(actions))
            return _step(actions, pre_action_masks=pre_action_masks)

        env.step = recording_step  # type: ignore[method-assign]

    class AlwaysPlayBot:
        @staticmethod
        def select_action(env, player_id, *, action_mask):
            del player_id
            legal = np.flatnonzero(action_mask[: env.action_space.no_op_action])
            assert len(legal)
            return int(legal[0])

    model = _tiny_model(builder)
    no_op = envs[0].action_space.no_op_action
    collect_rollout_stationary_opponents(
        envs=envs,
        learner_players=(0, 1),
        builder=builder,
        model=model,
        device=torch.device("cpu"),
        rollout_steps=1,
        recurrent_state=model.initial_state(2),
        previous_actions=np.full((2,), no_op, dtype=np.int64),
        previous_rewards=np.zeros((2,), dtype=np.float32),
        episode_starts=np.ones((2,), dtype=np.bool_),
        opponent_model=None,
        opponent_recurrent_state=None,
        opponent_previous_actions=np.full((2,), no_op, dtype=np.int64),
        opponent_previous_rewards=np.zeros((2,), dtype=np.float32),
        opponent_episode_starts=np.ones((2,), dtype=np.bool_),
        quiet_engine=True,
        opponent_bot=AlwaysPlayBot(),  # type: ignore[arg-type]
    )

    assert envs[0].defense_scenario is not None
    assert envs[1].defense_scenario is None
    assert recorded_actions[0][1] == no_op
    assert recorded_actions[1][0] != no_op


def test_inference_mode_rollout_is_exact_and_recurrent_state_is_reusable(
    monkeypatch: pytest.MonkeyPatch,
):
    def collect(use_inference_mode: bool, recurrent_state=None):
        monkeypatch.setattr(
            train_recurrent_module,
            "_USE_ROLLOUT_INFERENCE_MODE",
            use_inference_mode,
        )
        torch.manual_seed(9979)
        env = SelfPlayBattleEnv(seed=9979, max_ticks=128)
        builder = StructuredObservationBuilder(
            decks_path="decks.json", max_entities=128
        )
        env._structured_obs_builder = builder
        env.reset()
        model = _tiny_model(builder)
        no_op = env.action_space.no_op_action
        return collect_rollout_stationary_opponents(
            envs=[env],
            learner_players=(0,),
            builder=builder,
            model=model,
            device=torch.device("cpu"),
            rollout_steps=2,
            recurrent_state=(
                model.initial_state(1) if recurrent_state is None else recurrent_state
            ),
            previous_actions=np.full((1,), no_op, dtype=np.int64),
            previous_rewards=np.zeros((1,), dtype=np.float32),
            episode_starts=np.ones((1,), dtype=np.bool_),
            opponent_model=None,
            opponent_recurrent_state=None,
            opponent_previous_actions=np.full((1,), no_op, dtype=np.int64),
            opponent_previous_rewards=np.zeros((1,), dtype=np.float32),
            opponent_episode_starts=np.ones((1,), dtype=np.bool_),
            quiet_engine=True,
        )

    reference = collect(False)
    inference = collect(True)
    for name, value in vars(reference[0]).items():
        candidate = getattr(inference[0], name)
        if isinstance(value, np.ndarray):
            np.testing.assert_array_equal(candidate, value)
        else:
            assert candidate == value
    for reference_tensor, inference_tensor in zip(
        reference[1], inference[1], strict=True
    ):
        torch.testing.assert_close(inference_tensor, reference_tensor, rtol=0, atol=0)
    assert not reference[1][0].is_inference()
    assert inference[1][0].is_inference()
    continued = collect(True, inference[1])
    assert continued[1][0].is_inference()


def test_trimmed_rollout_entity_padding_preserves_deterministic_actions(
    monkeypatch: pytest.MonkeyPatch,
):
    envs = [SelfPlayBattleEnv(seed=9991 + index, max_ticks=128) for index in range(4)]
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    observations = []
    masks = []
    for index, env in enumerate(envs):
        env._structured_obs_builder = builder
        env.reset()
        player_id = index % 2
        observations.append(env.get_structured_observation(player_id))
        masks.append(env.get_action_mask(player_id))
    action_masks = np.stack(masks)
    no_op = envs[0].action_space.no_op_action
    previous_actions = np.full((len(envs),), no_op, dtype=np.int64)
    previous_rewards = np.zeros((len(envs),), dtype=np.float32)
    episode_starts = np.ones((len(envs),), dtype=np.bool_)

    monkeypatch.setattr(
        train_recurrent_module,
        "_USE_TRIMMED_ROLLOUT_ENTITY_PADDING",
        False,
    )
    dense = _stack_step_inputs(
        observations,
        action_masks,
        previous_actions,
        previous_rewards,
        episode_starts,
        torch.device("cpu"),
    )
    monkeypatch.setattr(
        train_recurrent_module,
        "_USE_TRIMMED_ROLLOUT_ENTITY_PADDING",
        True,
    )
    trimmed = _stack_step_inputs(
        observations,
        action_masks,
        previous_actions,
        previous_rewards,
        episode_starts,
        torch.device("cpu"),
    )
    assert trimmed.entity_ids.shape[-1] < dense.entity_ids.shape[-1]
    assert trimmed.critic_entity_ids.shape[-1] < dense.critic_entity_ids.shape[-1]

    torch.manual_seed(9991)
    model = _tiny_model(builder).eval()
    state = model.initial_state(len(envs))
    with torch.no_grad():
        dense_output = model(dense, state)
        trimmed_output = model(trimmed, state)
        dense_actions = model.act(dense, state, deterministic=True)[0]
        trimmed_actions = model.act(trimmed, state, deterministic=True)[0]
    torch.testing.assert_close(
        trimmed_output.joint_logits,
        dense_output.joint_logits,
        rtol=1e-5,
        atol=1e-5,
    )
    torch.testing.assert_close(trimmed_actions, dense_actions, rtol=0, atol=0)


def test_exact_simulator_step_inputs_supply_confidence_for_opt_in_policy():
    env = SelfPlayBattleEnv(seed=9992, max_ticks=128)
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=16)
    env._structured_obs_builder = builder
    env.reset()
    observation = env.get_structured_observation(0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action], dtype=np.int64),
        np.zeros((1,), dtype=np.float32),
        np.ones((1,), dtype=np.bool_),
        torch.device("cpu"),
        public_observation_confidence=True,
    )

    assert inputs.entity_id_confidence is not None
    assert inputs.entity_feature_confidence is not None
    assert inputs.hand_id_confidence is not None
    assert inputs.global_feature_confidence is not None
    torch.testing.assert_close(
        inputs.entity_id_confidence,
        inputs.entity_mask.to(torch.float32),
    )
    assert not bool(
        inputs.entity_feature_confidence[~inputs.entity_mask].count_nonzero()
    )
    assert bool(inputs.hand_id_confidence.eq(1).all())
    assert bool(inputs.global_feature_confidence.eq(1).all())

    model = ClasherPolicy(
        replace(
            _tiny_model(builder).config,
            public_observation_confidence=True,
        ),
        builder.card_stat_features,
    ).eval()
    with torch.no_grad():
        output = model(inputs)
    assert torch.isfinite(output.joint_logits[inputs.action_mask]).all()


def test_random_opponent_does_not_build_unused_structured_observations(monkeypatch):
    env = SelfPlayBattleEnv(seed=41, max_ticks=128)
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    env._structured_obs_builder = builder
    env.reset()
    model = _tiny_model(builder)
    no_op = env.action_space.no_op_action
    build_calls = 0
    original_build = builder.build

    def counted_build(battle, player_id):
        nonlocal build_calls
        build_calls += 1
        return original_build(battle, player_id)

    monkeypatch.setattr(builder, "build", counted_build)
    collect_rollout_stationary_opponents(
        envs=[env],
        learner_players=(0,),
        builder=builder,
        model=model,
        device=torch.device("cpu"),
        rollout_steps=2,
        recurrent_state=model.initial_state(1),
        previous_actions=np.full((1,), no_op, dtype=np.int64),
        previous_rewards=np.zeros((1,), dtype=np.float32),
        episode_starts=np.ones((1,), dtype=np.bool_),
        opponent_model=None,
        opponent_recurrent_state=None,
        opponent_previous_actions=np.full((1,), no_op, dtype=np.int64),
        opponent_previous_rewards=np.zeros((1,), dtype=np.float32),
        opponent_episode_starts=np.ones((1,), dtype=np.bool_),
        quiet_engine=True,
    )

    # One learner observation per step plus the learner bootstrap observation.
    assert build_calls == 3


def test_policy_temperature_concentrates_behavior_and_preserves_default() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = _tiny_model(builder)
    type_logits = torch.tensor([[[0.0, 0.0, 0.0, 0.0, 0.5, -2.0]]])
    location_logits = torch.zeros((1, 1, 4, 576))
    mask = torch.zeros((1, 1, 2306), dtype=torch.bool)
    mask[..., 0] = True
    mask[..., 576] = True
    mask[..., 1152] = True
    mask[..., 1728] = True
    mask[..., 2304] = True
    output = PolicyOutput(
        joint_logits=model._joint_action_logits(type_logits, location_logits, mask),
        values=torch.zeros((1, 1)),
        opponent_hand_logits=torch.zeros((1, 1, builder.spec.num_tokens)),
        opponent_elixir=torch.zeros((1, 1)),
        next_state=(torch.zeros((1, 1)), torch.zeros((1, 1))),
        action_type_logits=type_logits,
        location_logits=location_logits,
        deterministic_timing_logits=torch.tensor(
            [[[2.0, 2.0, 2.0, 2.0, 0.5, -2.0]]]
        ),
    )

    default = output.distribution()
    unit = output.distribution(temperature=1.0)
    cold = output.distribution(temperature=0.25)
    forced_play = output.distribution(
        temperature=0.25,
        force_play=torch.ones((1, 1), dtype=torch.bool),
    )
    forced_wait = output.distribution(
        temperature=0.25,
        force_play=torch.zeros((1, 1), dtype=torch.bool),
    )
    torch.testing.assert_close(default.probs, unit.probs)
    assert cold.probs[..., :2304].sum().item() > unit.probs[..., :2304].sum().item()
    assert cold.probs[..., 2304].item() < unit.probs[..., 2304].item()
    torch.testing.assert_close(
        forced_play.probs[..., :2304].sum(), torch.tensor(1.0)
    )
    torch.testing.assert_close(
        forced_wait.probs[..., 2304:].sum(), torch.tensor(1.0)
    )
    assert forced_play.probs[..., 2304:].count_nonzero().item() == 0
    assert forced_wait.probs[..., :2304].count_nonzero().item() == 0
    with pytest.raises(ValueError, match="finite and positive"):
        output.distribution(temperature=0.0)


def test_play_gate_does_not_aggregate_prepooled_timing_logit_twice() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=48,
            deterministic_hierarchy="play-gate",
        ),
        builder.card_stat_features,
    )
    type_logits = torch.tensor([[[-1.0, -1.0, -1.0, -1.0, 0.0, -5.0]]])
    location_logits = torch.zeros((1, 1, 4, 576))
    mask = torch.zeros((1, 1, 2306), dtype=torch.bool)
    mask[..., 0] = True
    mask[..., 576] = True
    mask[..., 1152] = True
    mask[..., 1728] = True
    mask[..., 2304] = True
    joint = model._joint_action_logits(type_logits, location_logits, mask)
    common = {
        "joint_logits": joint,
        "values": torch.zeros((1, 1)),
        "opponent_hand_logits": torch.zeros((1, 1, builder.spec.num_tokens)),
        "opponent_elixir": torch.zeros((1, 1)),
        "next_state": (torch.zeros((1, 1)), torch.zeros((1, 1))),
        "action_type_logits": type_logits,
        "location_logits": location_logits,
    }

    raw = PolicyOutput(**common)
    prepooled = PolicyOutput(
        **common,
        deterministic_timing_logits=type_logits.clone(),
    )

    # Four distinct slot logits represent four mutually exclusive ways to
    # play, so their raw probability mass beats wait after one aggregation.
    assert int(model._deterministic_actions(raw, mask).item()) < 2304
    # The prepooled head represents one play-mode logit copied four times; it
    # must be compared once, so wait (0.0) beats play (-1.0).
    assert int(model._deterministic_actions(prepooled, mask).item()) == 2304


def test_internal_event_mode_accumulates_factorized_play_probability() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=48,
            memory_kind="structured",
            hierarchical_mode_gate_enabled=True,
            deterministic_hierarchy="event",
            play_hazard_threshold=0.2,
        ),
        builder.card_stat_features,
    )
    type_logits = torch.full((1, 3, 6), -torch.inf)
    type_logits[..., 0] = torch.log(torch.tensor(0.1))
    type_logits[..., 4] = torch.log(torch.tensor(0.9))
    location_logits = torch.zeros((1, 3, 4, 576))
    mask = torch.zeros((1, 3, 2306), dtype=torch.bool)
    mask[..., 0] = True
    mask[..., 2304] = True
    output = PolicyOutput(
        joint_logits=torch.zeros((1, 3, 2306)),
        values=torch.zeros((1, 3)),
        opponent_hand_logits=torch.zeros((1, 3, builder.spec.num_tokens)),
        opponent_elixir=torch.zeros((1, 3)),
        next_state=(torch.zeros((1, 48)), torch.zeros((1, 48))),
        action_type_logits=type_logits,
        location_logits=location_logits,
        hierarchical_mode_logits=type_logits[..., (0, 4, 5)],
    )

    gates, accumulator = model._event_mode_force_gate(
        output, mask, torch.zeros(1)
    )
    assert gates.tolist() == [[False, False, True]]
    torch.testing.assert_close(accumulator, torch.zeros(1))

    inputs = PolicyInputs(
        entity_ids=torch.zeros((1, 3, 1), dtype=torch.long),
        entity_features=torch.zeros((1, 3, 1, 32)),
        entity_mask=torch.zeros((1, 3, 1), dtype=torch.bool),
        hand_ids=torch.ones((1, 3, 5), dtype=torch.long),
        global_features=torch.zeros((1, 3, 18)),
        action_mask=mask,
        previous_actions=torch.full((1, 3), 2304, dtype=torch.long),
        previous_rewards=torch.zeros((1, 3)),
        episode_starts=torch.tensor([[True, False, False]]),
    )
    with patch.object(model, "forward", return_value=output):
        actions, _log_prob, _values, next_state, _result = model.act(
            inputs, deterministic=True
        )
    assert actions.tolist() == [[2304, 2304, 0]]
    torch.testing.assert_close(next_state[0][:, -1], torch.zeros(1))


def test_internal_event_accumulator_persists_across_policy_calls() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=48,
            memory_kind="structured",
            hierarchical_mode_gate_enabled=True,
            deterministic_hierarchy="event",
            play_hazard_threshold=0.2,
        ),
        builder.card_stat_features,
    ).eval()
    assert model.hierarchical_mode_gate is not None
    output = model.hierarchical_mode_gate[-1]
    assert isinstance(output, torch.nn.Linear)
    with torch.no_grad():
        output.weight.zero_()
        output.bias.copy_(torch.tensor([np.log(0.1), np.log(0.9), 0.0]))
    mask = torch.zeros((1, 1, 2306), dtype=torch.bool)
    mask[..., 0] = True
    mask[..., 2304] = True
    state = model.initial_state(1, device="cpu")
    actions = []
    for step in range(3):
        inputs = PolicyInputs(
            entity_ids=torch.zeros((1, 1, 1), dtype=torch.long),
            entity_features=torch.zeros((1, 1, 1, 32)),
            entity_mask=torch.zeros((1, 1, 1), dtype=torch.bool),
            hand_ids=torch.ones((1, 1, 5), dtype=torch.long),
            global_features=torch.zeros((1, 1, 18)),
            action_mask=mask,
            previous_actions=torch.full((1, 1), 2304, dtype=torch.long),
            previous_rewards=torch.zeros((1, 1)),
            episode_starts=torch.tensor([[step == 0]]),
        )
        action, _log_prob, _value, state, _output = model.act(
            inputs, state, deterministic=True
        )
        actions.append(int(action.item()))
    assert actions == [2304, 2304, 0]
    torch.testing.assert_close(state[0][:, -1], torch.zeros(1), atol=1e-6, rtol=0.0)


def test_action_value_head_starts_behavior_closed() -> None:
    env = SelfPlayBattleEnv(seed=13, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    env._structured_obs_builder = builder
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=48,
            action_value_head_enabled=True,
        ),
        builder.card_stat_features,
    ).eval()
    observation = builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        env.get_action_mask(0)[None, :],
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        before = model(inputs)
        assert before.action_values is not None
        assert model.action_value_head is not None
        for parameter in model.action_value_head.parameters():
            parameter.add_(torch.randn_like(parameter) * 5.0)
        closed = model(inputs)
        assert closed.action_values is not None
        torch.testing.assert_close(before.joint_logits, closed.joint_logits)
        assert not torch.equal(before.action_values, closed.action_values)
        assert model.action_value_policy_gate is not None
        model.action_value_policy_gate.fill_(0.5)
        opened = model(inputs)
        assert not torch.equal(closed.joint_logits, opened.joint_logits)


def test_action_value_option_preserves_same_seed_shared_initialization() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    common = {
        "num_tokens": builder.spec.num_tokens,
        "max_entities": builder.spec.max_entities,
        "d_model": 32,
        "num_heads": 4,
        "actor_layers": 1,
        "critic_layers": 1,
        "memory_size": 48,
    }
    torch.manual_seed(29)
    control = ClasherPolicy(PolicyConfig(**common), builder.card_stat_features)
    torch.manual_seed(29)
    candidate = ClasherPolicy(
        PolicyConfig(**common, action_value_head_enabled=True),
        builder.card_stat_features,
    )
    control_state = control.state_dict()
    candidate_state = candidate.state_dict()
    shared = sorted(set(control_state).intersection(candidate_state))
    assert shared
    for name in shared:
        torch.testing.assert_close(control_state[name], candidate_state[name], rtol=0, atol=0)
