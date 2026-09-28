from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from clasher.rl.causal_vision import (
    CausalVisionTracker,
    CurrentFramePublicSignals,
    current_frame_card_play_cues,
    current_frame_deployment_cues,
    parse_visible_battle_clock,
)
from clasher.rl.model import PolicyConfig
from clasher.rl.public_observation import (
    ConfidenceAwareActorObservation,
    validate_real_play_feature_contract,
)
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import ActorObservation
from clasher.rl.tv_royale_replay import TVRoyaleDetection


def _frame(
    *,
    x: float | None,
    y: float | None,
    hp: float | None,
    hand_slot_one: int,
    tower_hp: float | None,
) -> ConfidenceAwareActorObservation:
    entity_ids = np.zeros((3,), dtype=np.int64)
    entity_features = np.zeros((3, 32), dtype=np.float32)
    entity_mask = np.zeros((3,), dtype=np.bool_)
    entity_id_confidence = np.zeros((3,), dtype=np.float32)
    entity_feature_confidence = np.zeros((3, 32), dtype=np.float32)
    if x is not None and y is not None:
        entity_ids[0] = 10
        entity_mask[0] = True
        entity_id_confidence[0] = 0.9
        entity_features[0, 0:2] = (x, y)
        entity_features[0, 2] = 1.0
        entity_features[0, 4] = 1.0
        entity_features[0, 23:27] = (0.4, 0.3, 0.6, 0.2)
        entity_features[0, 30] = 0.7
        entity_feature_confidence[0, 0:2] = 0.9
        entity_feature_confidence[0, 2:9] = 0.9
        entity_feature_confidence[0, 23:27] = 0.8
        entity_feature_confidence[0, 30] = 0.8
        if hp is not None:
            entity_features[0, 9] = hp
            entity_feature_confidence[0, 9] = 0.75

    hand_ids = np.asarray([1, hand_slot_one, 3, 4, 0], dtype=np.int64)
    hand_confidence = np.asarray(
        [1.0, float(hand_slot_one != 0), 1.0, 1.0, 0.0], dtype=np.float32
    )
    globals_ = np.zeros((18,), dtype=np.float32)
    global_confidence = np.zeros((18,), dtype=np.float32)
    globals_[0:6] = (0.2, 0.8, 0.0, 0.0, 0.0, 0.6)
    global_confidence[0:6] = 1.0
    if tower_hp is not None:
        globals_[8] = tower_hp
        global_confidence[8] = 0.7
    result = ConfidenceAwareActorObservation(
        observation=ActorObservation(
            entity_ids=entity_ids,
            entity_features=entity_features,
            entity_mask=entity_mask,
            hand_ids=hand_ids,
            global_features=globals_,
            opponent_history_ids=np.zeros((0,), dtype=np.int64),
            opponent_history_ages=np.zeros((0,), dtype=np.float32),
            opponent_seen_card_ids=np.zeros((0,), dtype=np.int64),
        ),
        entity_id_confidence=entity_id_confidence,
        entity_feature_confidence=entity_feature_confidence,
        hand_id_confidence=hand_confidence,
        global_feature_confidence=global_confidence,
        opponent_history_confidence=np.zeros((0,), dtype=np.float32),
        opponent_seen_card_confidence=np.zeros((0,), dtype=np.float32),
    )
    validate_real_play_feature_contract(result)
    return result


def test_causal_tracker_derives_motion_and_carries_short_sensor_gaps() -> None:
    tracker = CausalVisionTracker(max_gap_frames=2, confidence_decay=0.8)
    first = tracker.update(
        _frame(x=0.20, y=0.30, hp=0.70, hand_slot_one=2, tower_hp=0.8),
        frame=10,
    )
    second = tracker.update(
        _frame(x=0.22, y=0.31, hp=None, hand_slot_one=0, tower_hp=None),
        frame=11,
    )

    assert first.observation.entity_mask.tolist() == [True, False, False]
    assert second.observation.entity_features[0, 9] == pytest.approx(0.70)
    assert second.entity_feature_confidence[0, 9] == pytest.approx(0.60)
    direction = np.asarray([0.02, 0.01]) / np.linalg.norm([0.02, 0.01])
    assert second.observation.entity_features[0, 27:29] == pytest.approx(direction)
    assert np.all(second.entity_feature_confidence[0, 27:29] > 0.0)
    assert second.observation.hand_ids[1] == 2
    assert second.hand_id_confidence[1] == pytest.approx(0.8)
    assert second.observation.global_features[8] == pytest.approx(0.8)
    assert second.global_feature_confidence[8] == pytest.approx(0.56)
    validate_real_play_feature_contract(second)

    occluded = tracker.update(
        _frame(x=None, y=None, hp=None, hand_slot_one=2, tower_hp=0.8),
        frame=12,
    )
    assert occluded.observation.entity_mask[0]
    assert occluded.entity_id_confidence[0] == pytest.approx(0.9 * 0.8)
    assert occluded.observation.entity_features[0, 0] == pytest.approx(0.24)

    expired = tracker.update(
        _frame(x=None, y=None, hp=None, hand_slot_one=2, tower_hp=0.8),
        frame=14,
    )
    assert not expired.observation.entity_mask.any()


def test_causal_tracker_rejects_nonchronological_frames() -> None:
    tracker = CausalVisionTracker()
    source = _frame(x=None, y=None, hp=None, hand_slot_one=2, tower_hp=0.8)
    tracker.update(source, frame=5)
    with pytest.raises(ValueError, match="strictly increasing"):
        tracker.update(source, frame=5)


def test_causal_tracker_does_not_invent_motion_from_missing_position_axis() -> None:
    tracker = CausalVisionTracker()
    tracker.update(
        _frame(x=0.01, y=0.0, hp=0.7, hand_slot_one=2, tower_hp=0.8),
        frame=10,
    )
    source = _frame(x=0.0, y=0.0, hp=0.7, hand_slot_one=2, tower_hp=0.8)
    confidence = source.entity_feature_confidence.copy()
    confidence[0, 1] = 0.0
    source = replace(source, entity_feature_confidence=confidence)
    validate_real_play_feature_contract(source)

    tracked = tracker.update(source, frame=11)

    assert tracked.observation.entity_features[0, 27:29].tolist() == [0.0, 0.0]
    assert tracked.entity_feature_confidence[0, 27:29].tolist() == [0.0, 0.0]
    validate_real_play_feature_contract(tracked)


def test_causal_tracker_requires_temporal_confirmation_for_effects() -> None:
    source = _frame(
        x=0.4,
        y=0.5,
        hp=None,
        hand_slot_one=2,
        tower_hp=0.8,
    )
    features = source.observation.entity_features.copy()
    confidence = source.entity_feature_confidence.copy()
    features[0, 4] = 0.0
    features[0, 7] = 1.0
    confidence[0, 4:9] = 0.9
    effect = replace(
        source,
        observation=replace(source.observation, entity_features=features),
        entity_feature_confidence=confidence,
    )
    validate_real_play_feature_contract(effect)

    tracker = CausalVisionTracker(minimum_effect_observations=2)
    first = tracker.update(effect, frame=10)
    second = tracker.update(effect, frame=11)

    assert not first.observation.entity_mask.any()
    assert second.observation.entity_mask[0]
    assert second.observation.entity_features[0, 7] == 1.0


def test_causal_policy_config_requires_explicit_confidence_inputs() -> None:
    with pytest.raises(ValueError, match="requires public_observation_confidence"):
        PolicyConfig(
            num_tokens=12,
            max_entities=8,
            actor_observation_domain="causal-vision-v1",
        )


def test_selfplay_causal_actor_keeps_exact_state_only_in_critic() -> None:
    env = SelfPlayBattleEnv(seed=1701, max_ticks=64)
    env.reset()
    exact = env.get_structured_observation(0)
    causal = env.get_structured_observation(
        0, actor_observation_domain="causal-vision-v1"
    )
    repeated = env.get_structured_observation(
        0, actor_observation_domain="causal-vision-v1"
    )

    assert repeated is causal
    assert causal.entity_id_confidence is not None
    assert causal.entity_feature_confidence is not None
    assert causal.hand_id_confidence is not None
    assert causal.global_feature_confidence is not None
    assert np.array_equal(causal.critic_entity_ids, exact.critic_entity_ids)
    assert np.array_equal(causal.critic_entity_features, exact.critic_entity_features)
    assert np.array_equal(causal.critic_card_ids, exact.critic_card_ids)
    # Exact status/timer features cannot leak into the causal actor.
    assert not np.any(causal.entity_feature_confidence[..., 10:23])
    assert not np.any(causal.global_feature_confidence[..., 14:17])

    noop = env.action_space.no_op_action
    env.step({0: noop, 1: noop})
    advanced = env.get_structured_observation(
        0, actor_observation_domain="causal-vision-v1"
    )
    assert advanced is not causal


def test_causal_frame_actor_does_not_use_external_temporal_tracker() -> None:
    env = SelfPlayBattleEnv(seed=1702, max_ticks=64)
    env.reset()

    frame = env.get_structured_observation(
        0,
        actor_observation_domain="causal-frame-v1",
    )
    repeated = env.get_structured_observation(
        0,
        actor_observation_domain="causal-frame-v1",
    )

    assert repeated is frame
    assert env._causal_vision_trackers[0]._last_frame is None
    assert frame.entity_id_confidence is not None
    assert frame.entity_feature_confidence is not None
    assert frame.global_feature_confidence is not None
    validate_real_play_feature_contract(
        ConfidenceAwareActorObservation(
            observation=ActorObservation(
                entity_ids=frame.entity_ids,
                entity_features=frame.entity_features,
                entity_mask=frame.entity_mask,
                hand_ids=frame.hand_ids,
                global_features=frame.global_features,
                opponent_history_ids=frame.opponent_history_ids,
                opponent_history_ages=frame.opponent_history_ages,
                opponent_seen_card_ids=frame.opponent_seen_card_ids,
            ),
            entity_id_confidence=frame.entity_id_confidence,
            entity_feature_confidence=frame.entity_feature_confidence,
            hand_id_confidence=frame.hand_id_confidence,
            global_feature_confidence=frame.global_feature_confidence,
            opponent_history_confidence=np.zeros_like(
                frame.opponent_history_ages,
                dtype=np.float32,
            ),
            opponent_seen_card_confidence=np.zeros_like(
                frame.opponent_seen_card_ids,
                dtype=np.float32,
            ),
        )
    )


def test_visible_clock_parser_preserves_public_timer_and_fails_closed() -> None:
    regulation = parse_visible_battle_clock("0:12", confidence=0.91)
    overtime = parse_visible_battle_clock("Overtime 1:54", confidence=0.83)

    assert regulation is not None
    assert regulation.seconds_remaining == 12
    assert not regulation.overtime
    assert regulation.confidence == pytest.approx(0.91)
    assert overtime is not None
    assert overtime.seconds_remaining == 114
    assert overtime.overtime
    assert parse_visible_battle_clock("1:72", confidence=0.9) is None
    assert parse_visible_battle_clock("battle ends", confidence=0.9) is None
    with pytest.raises(ValueError, match="confidence"):
        parse_visible_battle_clock("1:00", confidence=1.1)


def test_current_frame_contract_rejects_external_history_and_motion() -> None:
    source = _frame(x=0.4, y=0.5, hp=0.8, hand_slot_one=2, tower_hp=0.7)
    pure = CurrentFramePublicSignals(observation=source)
    pure.validate()

    history = replace(
        source,
        observation=replace(
            source.observation,
            opponent_history_ids=np.asarray([10], dtype=np.int64),
            opponent_history_ages=np.asarray([0.0], dtype=np.float32),
        ),
        opponent_history_confidence=np.asarray([0.8], dtype=np.float32),
    )
    with pytest.raises(ValueError, match="externally accumulated opponent history"):
        CurrentFramePublicSignals(observation=history).validate()

    features = source.observation.entity_features.copy()
    feature_confidence = source.entity_feature_confidence.copy()
    features[0, 27:29] = (1.0, 0.0)
    feature_confidence[0, 27:29] = 0.7
    motion = replace(
        source,
        observation=replace(source.observation, entity_features=features),
        entity_feature_confidence=feature_confidence,
    )
    with pytest.raises(ValueError, match="externally tracked motion"):
        CurrentFramePublicSignals(observation=motion).validate()


def test_current_frame_marker_cues_preserve_boxes_as_visual_evidence_only() -> None:
    detections = [
        TVRoyaleDetection("clock", 1, 0.91, 90, 190, 110, 210),
        TVRoyaleDetection("clock", 1, 0.83, 94, 193, 112, 211),
        TVRoyaleDetection("clock", 0, 0.92, 250, 480, 266, 498),
        TVRoyaleDetection("bar", 1, 0.99, 90, 180, 130, 190),
    ]

    cues = current_frame_deployment_cues(
        detections,
        image_width=428,
        image_height=683,
    )

    assert len(cues) == 2
    enemy, own = cues
    assert enemy.player_id == 0
    assert own.player_id == 1
    assert own.support == 2
    assert own.x == pytest.approx(100.0 / 428, abs=0.01)
    assert own.y == pytest.approx(200.0 / 683, abs=0.01)
    assert 0.0 < own.visual_extent_x < 0.1
    assert 0.0 < own.visual_extent_y < 0.1


def test_current_frame_card_play_cue_is_unambiguous_and_not_deduplicated() -> None:
    marker_detection = TVRoyaleDetection("clock", 1, 0.94, 90, 190, 110, 210)
    hog = TVRoyaleDetection("hog-rider", 1, 0.90, 92, 194, 118, 230)
    markers = current_frame_deployment_cues(
        [marker_detection, hog], image_width=428, image_height=683
    )
    token_ids = {"hog-rider": 17, "knight": 23}
    cues = current_frame_card_play_cues(
        [marker_detection, hog],
        markers,
        image_width=428,
        image_height=683,
        card_token=token_ids.get,
    )

    assert len(cues) == 1
    assert cues[0].card_token_id == 17
    assert cues[0].player_id == 1
    assert cues[0].event_confidence == pytest.approx(0.90)
    # The pure current-frame extractor intentionally repeats identical visual
    # evidence. Only the model-owned recurrent state may suppress a duplicate.
    assert current_frame_card_play_cues(
        [marker_detection, hog],
        markers,
        image_width=428,
        image_height=683,
        card_token=token_ids.get,
    ) == cues

    ambiguous = current_frame_card_play_cues(
        [
            marker_detection,
            hog,
            TVRoyaleDetection("knight", 1, 0.95, 95, 196, 120, 232),
        ],
        markers,
        image_width=428,
        image_height=683,
        card_token=token_ids.get,
    )
    assert ambiguous == ()
