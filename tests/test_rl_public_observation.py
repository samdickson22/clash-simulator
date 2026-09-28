from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from clasher.rl.public_observation import (
    PublicObservationDegradationProfile,
    degrade_simulator_public_observation,
    exact_public_observation,
    validate_real_play_feature_contract,
)
from clasher.rl.structured_obs import ActorObservation


def _actor_observation() -> ActorObservation:
    return ActorObservation(
        entity_ids=np.asarray([3, 0], dtype=np.int64),
        entity_features=np.asarray([[0.25, 0.75], [0.0, 0.0]], dtype=np.float32),
        entity_mask=np.asarray([True, False], dtype=np.bool_),
        hand_ids=np.asarray([4, 5, 0], dtype=np.int64),
        global_features=np.asarray([0.5, 0.0], dtype=np.float32),
        opponent_history_ids=np.asarray([7, 0], dtype=np.int64),
        opponent_history_ages=np.asarray([0.2, 0.0], dtype=np.float32),
        opponent_seen_card_ids=np.asarray([7, 8], dtype=np.int64),
    )


def test_exact_public_observation_marks_simulator_values_known() -> None:
    result = exact_public_observation(_actor_observation())

    assert result.entity_id_confidence.tolist() == [1.0, 0.0]
    assert result.entity_feature_confidence.tolist() == [[1.0, 1.0], [0.0, 0.0]]
    assert np.all(result.hand_id_confidence == 1.0)
    assert np.all(result.global_feature_confidence == 1.0)
    assert np.all(result.opponent_history_confidence == 1.0)
    assert np.all(result.opponent_seen_card_confidence == 1.0)


def test_public_observation_rejects_fabricated_missing_value() -> None:
    exact = exact_public_observation(_actor_observation())
    confidence = exact.entity_feature_confidence.copy()
    confidence[0, 0] = 0.0
    invalid = replace(exact, entity_feature_confidence=confidence)

    with pytest.raises(ValueError, match="fabricates values"):
        invalid.validate()


def test_public_observation_rejects_confidence_shape_mismatch() -> None:
    exact = exact_public_observation(_actor_observation())
    invalid = replace(
        exact,
        hand_id_confidence=np.ones((2,), dtype=np.float32),
    )

    with pytest.raises(ValueError, match="shape"):
        invalid.validate()


def test_real_play_contract_rejects_exact_simulator_status_and_clocks() -> None:
    features = np.zeros((1, 32), dtype=np.float32)
    features[0, 2] = 1.0
    features[0, 4] = 1.0
    features[0, 14] = 0.5
    globals_ = np.zeros((18,), dtype=np.float32)
    globals_[16] = 0.4
    actor = ActorObservation(
        entity_ids=np.asarray([3], dtype=np.int64),
        entity_features=features,
        entity_mask=np.asarray([True], dtype=np.bool_),
        hand_ids=np.asarray([4, 5, 6, 7, 8], dtype=np.int64),
        global_features=globals_,
        opponent_history_ids=np.zeros((0,), dtype=np.int64),
        opponent_history_ages=np.zeros((0,), dtype=np.float32),
        opponent_seen_card_ids=np.zeros((0,), dtype=np.int64),
    )

    with pytest.raises(ValueError, match="stun_remaining.*next_card_refill"):
        validate_real_play_feature_contract(exact_public_observation(actor))


def test_simulator_degradation_matches_current_replay_visibility_contract() -> None:
    features = np.zeros((3, 32), dtype=np.float32)
    features[0, 0:2] = (0.25, 0.75)
    features[0, 2] = 1.0
    features[0, 4] = 1.0  # troop
    features[0, 9] = 0.55
    features[0, 14] = 0.5  # exact stun state is not yet visually decoded
    features[0, 23:27] = (0.4, 0.3, 0.6, 0.2)
    features[0, 27:29] = (1.0, 0.0)
    features[0, 30] = 0.7
    features[1, 3] = 1.0
    features[1, 6] = 1.0  # visually detectable projectile/effect
    actor = ActorObservation(
        entity_ids=np.asarray([10, 11, 0], dtype=np.int64),
        entity_features=features,
        entity_mask=np.asarray([True, True, False], dtype=np.bool_),
        hand_ids=np.asarray([2, 3, 4, 5, 6], dtype=np.int64),
        global_features=np.linspace(0.0, 1.0, 18, dtype=np.float32),
        opponent_history_ids=np.asarray([8, 9], dtype=np.int64),
        opponent_history_ages=np.asarray([0.1, 0.2], dtype=np.float32),
        opponent_seen_card_ids=np.asarray([8, 9], dtype=np.int64),
    )
    profile = PublicObservationDegradationProfile(
        entity_keep_probability=1.0,
        hp_keep_probability=1.0,
        motion_keep_probability=1.0,
        tower_hp_keep_probability=1.0,
    )

    first = degrade_simulator_public_observation(
        actor, profile=profile, rng=np.random.default_rng(101)
    )
    second = degrade_simulator_public_observation(
        actor, profile=profile, rng=np.random.default_rng(101)
    )

    assert np.array_equal(first.observation.entity_features, second.observation.entity_features)
    assert first.observation.entity_mask.tolist() == [True, True, False]
    assert first.observation.entity_features[0, 9] == pytest.approx(0.55)
    assert first.entity_feature_confidence[0, 9] == pytest.approx(0.69)
    assert first.observation.entity_features[0, 14] == 0.0
    assert first.entity_feature_confidence[0, 14] == 0.0
    assert first.observation.entity_features[0, 27:29].tolist() == [1.0, 0.0]
    assert first.observation.entity_features[1, 6] == 1.0
    assert first.entity_feature_confidence[1, 6] > 0.0
    assert first.entity_feature_confidence[1, 9] == 0.0
    assert first.observation.hand_ids.tolist() == [2, 3, 4, 5, 6]
    assert first.hand_id_confidence.tolist() == [1.0, 1.0, 1.0, 1.0, 1.0]
    assert first.observation.global_features[6] == 0.0
    assert first.global_feature_confidence[6] == 0.0
    assert np.all(first.global_feature_confidence[8:14] == pytest.approx(0.69))
    assert not first.observation.opponent_history_ids.any()
    assert not first.opponent_history_confidence.any()


def test_simulator_degradation_profile_rejects_invalid_coverage() -> None:
    with pytest.raises(ValueError, match="hp_keep_probability"):
        PublicObservationDegradationProfile(hp_keep_probability=1.1).validate()


def test_real_play_contract_accepts_public_next_card_and_rejects_later_cards() -> None:
    actor = ActorObservation(
        entity_ids=np.zeros((1,), dtype=np.int64),
        entity_features=np.zeros((1, 32), dtype=np.float32),
        entity_mask=np.zeros((1,), dtype=np.bool_),
        hand_ids=np.asarray([2, 3, 4, 5, 6, 7], dtype=np.int64),
        global_features=np.zeros((18,), dtype=np.float32),
        opponent_history_ids=np.zeros((0,), dtype=np.int64),
        opponent_history_ages=np.zeros((0,), dtype=np.float32),
        opponent_seen_card_ids=np.zeros((0,), dtype=np.int64),
    )
    public = degrade_simulator_public_observation(
        actor,
        profile=PublicObservationDegradationProfile(),
        rng=np.random.default_rng(17),
    )
    assert public.observation.hand_ids.tolist() == [2, 3, 4, 5, 6, 0]
    assert public.hand_id_confidence.tolist() == [1.0, 1.0, 1.0, 1.0, 1.0, 0.0]

    hidden_hand = public.observation.hand_ids.copy()
    hidden_hand[5] = 7
    hidden_confidence = public.hand_id_confidence.copy()
    hidden_confidence[5] = 1.0
    invalid = replace(
        public,
        observation=replace(public.observation, hand_ids=hidden_hand),
        hand_id_confidence=hidden_confidence,
    )

    with pytest.raises(ValueError, match="beyond hand plus public next card"):
        validate_real_play_feature_contract(invalid)
