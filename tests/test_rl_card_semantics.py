from __future__ import annotations

import math

import numpy as np
import torch

from clasher.rl.card_semantics import (
    SEMANTIC_EXTRA_FEATURE_NAMES,
    SEMANTIC_FEATURE_NAMES,
    semantic_card_profile,
    semantic_distance,
)
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder


def test_semantic_features_are_finite_and_versioned_by_name() -> None:
    profile = semantic_card_profile("RoyalGiant")

    assert profile.vector.shape == (len(SEMANTIC_FEATURE_NAMES),)
    assert np.isfinite(profile.vector).all()
    assert profile.role == "building_target"
    assert profile.vector[SEMANTIC_FEATURE_NAMES.index("targets_buildings_only")] == 1
    assert profile.vector[SEMANTIC_FEATURE_NAMES.index("attack_range")] > 0


def test_mechanically_related_win_conditions_share_a_finite_metric_space() -> None:
    giant = semantic_card_profile("Giant")
    royal_giant = semantic_card_profile("RoyalGiant")
    knight = semantic_card_profile("Knight")

    assert semantic_distance(giant, royal_giant) < 2.0
    assert math.isinf(semantic_distance(giant, knight))


def test_spell_roles_separate_spawn_control_and_damage_payloads() -> None:
    assert semantic_card_profile("Graveyard").role == "spawn_spell"
    assert semantic_card_profile("Freeze").role == "control_spell"
    assert semantic_card_profile("Fireball").role == "damage_spell"
    assert semantic_card_profile("Zap").role == "small_spell"


def test_builder_preserves_v1_and_versions_richer_descriptors() -> None:
    legacy = StructuredObservationBuilder(card_vocab=["Giant", "RoyalGiant"])
    semantic = StructuredObservationBuilder(
        card_vocab=["Giant", "RoyalGiant"],
        card_semantics_version=2,
    )
    residual = StructuredObservationBuilder(
        card_vocab=["Giant", "RoyalGiant"],
        card_semantics_version=3,
    )

    assert legacy.card_stat_features.shape[1] == 16
    assert semantic.card_stat_features.shape[1] == len(SEMANTIC_FEATURE_NAMES)
    assert residual.card_stat_features.shape[1] == 16 + len(
        SEMANTIC_EXTRA_FEATURE_NAMES
    )
    np.testing.assert_array_equal(
        residual.card_stat_features[:, :16],
        legacy.card_stat_features,
    )
    giant = semantic.card_stat_features[semantic.token_id("Giant")]
    royal_giant = semantic.card_stat_features[semantic.token_id("RoyalGiant")]
    assert np.linalg.norm(giant - royal_giant) < 2.0


def test_old_checkpoint_without_semantics_version_loads_as_v1(tmp_path) -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=8)
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.max_entities,
        d_model=16,
        num_heads=2,
        actor_layers=1,
        critic_layers=1,
        memory_size=16,
    )
    model = ClasherPolicy(config, builder.card_stat_features)
    payload_config = config.to_dict()
    payload_config.pop("card_semantics_version")
    checkpoint = tmp_path / "legacy.pt"
    torch.save(
        {
            "format_version": 2,
            "model_config": payload_config,
            "token_names": builder.token_names,
            "model_state_dict": model.state_dict(),
        },
        checkpoint,
    )

    loaded = load_policy_checkpoint(
        checkpoint,
        device=torch.device("cpu"),
        decks_path="decks.json",
    )

    assert loaded.model.config.card_semantics_version == 1
    assert loaded.builder.card_stat_features.shape[1] == 16
