from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
import torch

from clasher.rl.imitation import load_public_observation_sidecar
from clasher.rl.model import PolicyConfig
from clasher.rl.public_action_mask import PUBLIC_ACTION_MASK_CONTRACT_VERSION
from clasher.rl.public_observation import (
    ENTITY_FEATURE_NAMES,
    GLOBAL_FEATURE_NAMES,
    TV_ROYALE_PILOT_DEGRADATION,
    ConfidenceAwareActorObservation,
    validate_real_play_feature_contract,
)
from clasher.rl.structured_obs import ActorObservation

CHECKPOINT = Path(
    "checkpoints/fresh_structured_causal_v1_seed1062701/"
    "resource_belief_gated_seed1063602/resource_u10_gate0.pt"
)
CHECKPOINT_SHA256 = (
    "3353615954fdcfdb24f2ba570f1888cd6130242238391a9bcf98dcedbcfc5b88"
)

# Every feature receives an explicit audit disposition.  This prevents schema
# growth from silently bypassing the train/live equivalence matrix.
ENTITY_DISPOSITIONS = (
    "randomize",  # x
    "randomize",  # y
    "randomize",  # own_team
    "randomize",  # enemy_team
    "randomize",  # troop_kind
    "randomize",  # building_kind
    "randomize",  # projectile_kind
    "randomize",  # area_effect_kind
    "keep_zero",  # other_kind
    "randomize",  # hp_fraction
    "keep_zero",  # shield_fraction
    "keep_zero",  # airborne
    "keep_zero",  # deployment_pending
    "keep_zero",  # deployment_remaining_fraction
    "keep_zero",  # stun_remaining
    "keep_zero",  # slow_remaining
    "keep_zero",  # haste_remaining
    "keep_zero",  # special_move_active
    "keep_zero",  # stealth_active
    "keep_zero",  # hidden_building
    "keep_zero",  # forced_movement
    "keep_zero",  # attack_windup
    "keep_zero",  # charging
    "drop_or_internalize",  # base_speed
    "drop_or_internalize",  # attack_range
    "drop_or_internalize",  # sight_range
    "drop_or_internalize",  # collision_radius
    "drop_or_redefine",  # motion_x
    "drop_or_redefine",  # motion_y
    "keep_zero",  # effect_progress
    "drop_or_internalize",  # base_damage
    "keep_zero",  # tower_active
)
GLOBAL_DISPOSITIONS = (
    "model_clock",  # battle_progress
    "model_clock",  # battle_remaining
    "model_clock",  # double_elixir
    "model_clock",  # triple_elixir
    "model_clock",  # overtime
    "randomize",  # own_elixir
    "keep_zero",  # own_crowns
    "keep_zero",  # enemy_crowns
    "randomize",  # own_left_tower_hp
    "randomize",  # own_right_tower_hp
    "randomize",  # own_king_tower_hp
    "randomize",  # enemy_left_tower_hp
    "randomize",  # enemy_right_tower_hp
    "randomize",  # enemy_king_tower_hp
    "keep_zero",  # champion_cooldown
    "keep_zero",  # champion_duration
    "keep_zero",  # next_card_refill
    "keep_zero",  # enemy_king_alive
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_equivalence_matrix_covers_every_actor_scalar_feature() -> None:
    assert len(ENTITY_FEATURE_NAMES) == len(ENTITY_DISPOSITIONS) == 32
    assert len(GLOBAL_FEATURE_NAMES) == len(GLOBAL_DISPOSITIONS) == 18
    assert set(ENTITY_DISPOSITIONS) == {
        "randomize",
        "keep_zero",
        "drop_or_internalize",
        "drop_or_redefine",
    }
    assert set(GLOBAL_DISPOSITIONS) == {
        "model_clock",
        "randomize",
        "keep_zero",
    }


def test_accepted_checkpoint_contract_and_confidence_usage_are_pinned() -> None:
    if not CHECKPOINT.is_file():
        pytest.skip("accepted structured checkpoint is not present in this checkout")
    assert _sha256(CHECKPOINT) == CHECKPOINT_SHA256
    payload = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    config = PolicyConfig.from_dict(payload["model_config"])

    assert config.actor_observation_domain == "causal-frame-v1"
    assert config.public_observation_confidence is True
    assert config.memory_kind == "structured"
    assert config.memory_size == 64
    assert config.card_input_mode == "hybrid"
    assert config.card_semantics_version == 3
    assert config.public_history_slots == 0
    assert config.public_seen_card_slots == 0
    assert config.structured_deterministic_resource_enabled is False
    assert payload["args"]["actor_observation_domain"] == "simulator-exact"

    state = payload["model_state_dict"]
    assert float(state["structured_resource_policy_gate"].item()) == 0.0
    assert float(
        state["actor_encoder.card_confidence_projection.2.weight"].norm()
    ) == 0.0
    assert float(
        state["actor_encoder.entity_confidence_projection.2.weight"].norm()
    ) > 1.0
    assert float(
        state["actor_encoder.global_confidence_projection.2.weight"].norm()
    ) > 0.8


def test_accepted_simulator_degradation_is_exact_but_synthetic() -> None:
    profile = TV_ROYALE_PILOT_DEGRADATION
    assert profile.entity_keep_probability == 1.0
    assert profile.identity_confidence == 0.85
    assert profile.position_confidence == 0.85
    assert profile.static_feature_confidence == 0.85
    assert profile.hp_keep_probability == 0.66
    assert profile.hp_confidence == 0.69
    assert profile.motion_keep_probability == 0.36
    assert profile.motion_confidence == 0.60
    assert profile.tower_hp_keep_probability == 0.66
    assert profile.tower_hp_confidence == 0.69
    assert profile.position_noise_std == 0.0
    assert profile.hp_noise_std == 0.0


def test_inspected_causal_rehearsal_has_no_next_card_coverage() -> None:
    root = Path("datasets/derived/structured_oracle_mix_seed1063501")
    base_path = root / "mix_oracle3_12k.npz"
    public_path = root / "mix_oracle3_12k_public_v2.npz"
    if not base_path.is_file() or not public_path.is_file():
        pytest.skip("inspected oracle-mix lineage corpora are not present")
    with np.load(base_path, allow_pickle=False) as base:
        base_hand = np.asarray(base["hand_ids"])
    with np.load(public_path, allow_pickle=False) as public:
        public_hand = np.asarray(public["hand_ids"])
        public_confidence = np.asarray(public["hand_id_confidence"])

    assert base_hand.shape == public_hand.shape == (12288, 5)
    assert np.count_nonzero(base_hand[:, 4]) == 12288
    assert np.count_nonzero(public_hand[:, 4]) == 0
    assert np.count_nonzero(public_confidence[:, 4]) == 0


def test_sidecar_loader_and_public_validator_both_accept_visible_next_card(
    tmp_path: Path,
) -> None:
    hand_ids = np.asarray([[0, 0, 0, 0, 7]], dtype=np.int64)
    hand_confidence = np.asarray([[0.0, 0.0, 0.0, 0.0, 1.0]], dtype=np.float32)
    actor = ActorObservation(
        entity_ids=np.zeros((1,), dtype=np.int64),
        entity_features=np.zeros((1, 32), dtype=np.float32),
        entity_mask=np.zeros((1,), dtype=np.bool_),
        hand_ids=hand_ids[0],
        global_features=np.zeros((18,), dtype=np.float32),
        opponent_history_ids=np.zeros((0,), dtype=np.int64),
        opponent_history_ages=np.zeros((0,), dtype=np.float32),
        opponent_seen_card_ids=np.zeros((0,), dtype=np.int64),
    )
    public = ConfidenceAwareActorObservation(
        observation=actor,
        entity_id_confidence=np.zeros((1,), dtype=np.float32),
        entity_feature_confidence=np.zeros((1, 32), dtype=np.float32),
        hand_id_confidence=hand_confidence[0],
        global_feature_confidence=np.zeros((18,), dtype=np.float32),
        opponent_history_confidence=np.zeros((0,), dtype=np.float32),
        opponent_seen_card_confidence=np.zeros((0,), dtype=np.float32),
    )
    validate_real_play_feature_contract(public)

    sidecar = tmp_path / "public_v2.npz"
    np.savez_compressed(
        sidecar,
        schema_version=np.asarray(2, dtype=np.int64),
        feature_contract_version=np.asarray(2, dtype=np.int64),
        action_mask_contract_version=np.asarray(
            PUBLIC_ACTION_MASK_CONTRACT_VERSION, dtype=np.int64
        ),
        entity_ids=np.zeros((1, 1), dtype=np.int64),
        entity_features=np.zeros((1, 1, 32), dtype=np.float32),
        entity_mask=np.zeros((1, 1), dtype=np.bool_),
        entity_id_confidence=np.zeros((1, 1), dtype=np.float32),
        entity_feature_confidence=np.zeros((1, 1, 32), dtype=np.float32),
        hand_ids=hand_ids,
        hand_id_confidence=hand_confidence,
        global_features=np.zeros((1, 18), dtype=np.float32),
        global_feature_confidence=np.zeros((1, 18), dtype=np.float32),
        action_masks=np.ones((1, 2306), dtype=np.bool_),
        expert_action_masked=np.zeros((1,), dtype=np.bool_),
    )
    base_arrays = {
        "entity_ids": np.zeros((1, 1), dtype=np.int64),
        "entity_features": np.zeros((1, 1, 32), dtype=np.float32),
        "entity_mask": np.zeros((1, 1), dtype=np.bool_),
        "hand_ids": np.zeros((1, 5), dtype=np.int64),
        "global_features": np.zeros((1, 18), dtype=np.float32),
        "action_masks": np.ones((1, 2306), dtype=np.bool_),
        "previous_rewards": np.zeros((1,), dtype=np.float32),
        "expert_actions": np.zeros((1,), dtype=np.int64),
    }
    merged = load_public_observation_sidecar(sidecar, base_arrays=base_arrays)
    assert merged["hand_ids"][0, 4] == 7
    assert merged["hand_id_confidence"][0, 4] == 1.0
