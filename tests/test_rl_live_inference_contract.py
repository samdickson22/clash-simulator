from __future__ import annotations

import hashlib

import pytest

from clasher.rl.live_inference_contract import (
    InferenceContractError,
    ModelPrediction,
    PublicVisionFrame,
    evaluate_predictions,
    parse_evaluation_labels,
    parse_model_prediction,
    parse_public_vision_frame,
    run_public_inference,
)


def _vision(frame: str = "f0", timestamp_ms: int = 0) -> dict[str, object]:
    return {
        "schema_version": 1,
        "episode_id": "game-1",
        "frame_id": frame,
        "timestamp_ms": timestamp_ms,
        "public": {
            "visible_clock_seconds": 118.0,
            "clock_confidence": 0.9,
            "own_elixir": 6.0,
            "own_elixir_confidence": 0.95,
            "own_hand": ["Knight", "Archers", "Fireball", "HogRider"],
            "own_hand_confidence": [0.9, 0.91, 0.92, 0.93],
            "own_next_card": "Skeletons",
            "own_next_card_confidence": 0.81,
            "entities": [
                {
                    "track_id": "enemy-1",
                    "card": "HogRider",
                    "kind": "troop",
                    "player_id": 1,
                    "x_tiles": 8.5,
                    "y_tiles": 17.0,
                    "confidence": 0.88,
                    "hp_fraction": 0.75,
                    "hp_confidence": 0.79,
                    "statuses": ["slowed"],
                }
            ],
            "play_events": [
                {
                    "event_id": "play-4",
                    "player_id": 1,
                    "card": "HogRider",
                    "confidence": 0.91,
                    "x_tiles": 8.5,
                    "y_tiles": 17.0,
                }
            ],
        },
    }


def _prediction(frame: str = "f0", step: int = 0) -> dict[str, object]:
    return {
        "schema_version": 1,
        "episode_id": "game-1",
        "frame_id": frame,
        "state_step": step,
        "state_digest": hashlib.sha256(f"state-{step}".encode()).hexdigest(),
        "predictions": {
            "clock_seconds": 118.2,
            "opponent_elixir": 4.2,
            "cycle_plays_until_available": {"HogRider": 4},
            "placements": [{"event_id": "play-4", "x_tiles": 8.7, "y_tiles": 17.1}],
            "entity_hp": {"enemy-1": 0.72},
            "statuses": {"enemy-1": ["slowed"]},
        },
    }


def _labels(split: str = "chronology_test") -> dict[str, object]:
    return {
        "schema_version": 1,
        "split": split,
        "episode_id": "game-1",
        "frame_id": "f0",
        "labels": {
            "clock_seconds": 118.0,
            "opponent_elixir": 4.0,
            "cycle_plays_until_available": {"HogRider": 4},
            "placements": [{"event_id": "play-4", "x_tiles": 8.5, "y_tiles": 17.0}],
            "entity_hp": {"enemy-1": 0.75},
            "statuses": {"enemy-1": ["slowed"]},
        },
    }


def test_current_public_frame_schema_accepts_only_current_measurements() -> None:
    frame = parse_public_vision_frame(_vision())

    assert frame.frame_id == "f0"
    assert frame.own_hand == ("Knight", "Archers", "Fireball", "HogRider")
    assert frame.own_hand_confidence == pytest.approx((0.9, 0.91, 0.92, 0.93))
    assert frame.own_next_card == "Skeletons"
    assert frame.play_events[0].card == "HogRider"
    assert not hasattr(frame, "opponent_hand")
    assert not hasattr(frame, "history")


@pytest.mark.parametrize(
    "key,value",
    [
        ("battle_state", {"tick": 12}),
        ("publicCardPlayHistory", ["HogRider"]),
        ("opponent_hand", ["HogRider"]),
        ("exact_opponent_elixir", 4.0),
        ("critic_state", [1.0]),
        ("action_masks", [True, False]),
        ("opponent_history_ids", [7]),
        ("stun_remaining", 12),
    ],
)
def test_public_frame_rejects_privileged_fields_recursively(key: str, value: object) -> None:
    payload = _vision()
    public = payload["public"]
    assert isinstance(public, dict)
    public["entities"][0][key] = value  # type: ignore[index]

    with pytest.raises(InferenceContractError, match="privileged"):
        parse_public_vision_frame(payload)


def test_public_frame_rejects_battle_state_object_without_importing_battle() -> None:
    FakeBattleState = type("BattleState", (), {})
    payload = _vision()
    public = payload["public"]
    assert isinstance(public, dict)
    public["leak"] = FakeBattleState()

    with pytest.raises(InferenceContractError, match="BattleState"):
        parse_public_vision_frame(payload)


class _InternalCounterAdapter:
    def __init__(self) -> None:
        self.episode_id = ""
        self.step_number = 0
        self.received_types: list[type[object]] = []

    def reset(self, episode_id: str) -> None:
        self.episode_id = episode_id
        self.step_number = 0

    def step(self, frame: PublicVisionFrame) -> ModelPrediction:
        self.received_types.append(type(frame))
        frame_id = str(frame.frame_id)
        prediction = parse_model_prediction(_prediction(frame_id, self.step_number))
        self.step_number += 1
        return prediction


def test_runner_keeps_recurrent_state_inside_adapter_and_labels_outside() -> None:
    adapter = _InternalCounterAdapter()
    frames = [
        parse_public_vision_frame(_vision("f0", 0)),
        parse_public_vision_frame(_vision("f1", 100)),
    ]

    result = run_public_inference(adapter, frames)

    assert [row.state_step for row in result] == [0, 1]
    assert {kind.__name__ for kind in adapter.received_types} == {"PublicVisionFrame"}


def test_runner_fails_closed_on_state_step_or_time_discontinuity() -> None:
    adapter = _InternalCounterAdapter()
    frames = [
        parse_public_vision_frame(_vision("f0", 100)),
        parse_public_vision_frame(_vision("f1", 100)),
    ]
    with pytest.raises(InferenceContractError, match="timestamps"):
        run_public_inference(adapter, frames)


def test_runner_revalidates_direct_adapter_outputs() -> None:
    class InvalidAdapter(_InternalCounterAdapter):
        def step(self, frame: PublicVisionFrame) -> ModelPrediction:
            prediction = super().step(frame)
            return ModelPrediction(
                **{
                    **prediction.__dict__,
                    "opponent_elixir": 11.0,
                }
            )

    with pytest.raises(InferenceContractError, match="opponent elixir"):
        run_public_inference(
            InvalidAdapter(), [parse_public_vision_frame(_vision("f0", 0))]
        )


def test_heldout_evaluation_scores_all_six_trajectory_families() -> None:
    report = evaluate_predictions(
        [parse_model_prediction(_prediction())],
        [parse_evaluation_labels(_labels())],
    )

    assert report["passed"] is True
    assert report["contract"]["labels_exposed_during_inference"] is False
    assert report["metrics"]["clock"]["mae_seconds"] == pytest.approx(0.2)
    assert report["metrics"]["elixir"]["mae"] == pytest.approx(0.2)
    assert report["metrics"]["cycle"]["accuracy"] == 1.0
    assert report["metrics"]["placement"]["within_one_tile"] == 1.0
    assert report["metrics"]["hp"]["mae"] == pytest.approx(0.03)
    assert report["metrics"]["status"]["f1"] == 1.0


def test_evaluation_rejects_training_labels_and_missing_predictions() -> None:
    with pytest.raises(InferenceContractError, match="not held out"):
        parse_evaluation_labels(_labels("train"))

    labels = _labels()
    labels["frame_id"] = "missing"
    report = evaluate_predictions(
        [parse_model_prediction(_prediction())],
        [parse_evaluation_labels(labels)],
    )
    assert report["passed"] is False
    assert report["gate_checks"]["frame_coverage"] is False


def test_evaluation_rejects_fabricated_extra_placement() -> None:
    prediction = _prediction()
    prediction_payload = prediction["predictions"]
    assert isinstance(prediction_payload, dict)
    placements = prediction_payload["placements"]
    assert isinstance(placements, list)
    placements.append({"event_id": "invented", "x_tiles": 3.0, "y_tiles": 4.0})

    report = evaluate_predictions(
        [parse_model_prediction(prediction)],
        [parse_evaluation_labels(_labels())],
    )

    assert report["passed"] is False
    assert report["extra_values"]["placement"] == 1
    assert report["gate_checks"]["no_extra_values"] is False


def test_status_gate_counts_labelled_negative_frames() -> None:
    labels = _labels()
    labels_payload = labels["labels"]
    assert isinstance(labels_payload, dict)
    labels_payload["statuses"] = {"enemy-1": []}
    prediction = _prediction()
    prediction_payload = prediction["predictions"]
    assert isinstance(prediction_payload, dict)
    prediction_payload["statuses"] = {"enemy-1": []}

    report = evaluate_predictions(
        [parse_model_prediction(prediction)],
        [parse_evaluation_labels(labels)],
    )

    assert report["metrics"]["status"] == {"samples": 1, "f1": 1.0}
    assert report["gate_checks"]["status"] is True


def test_prediction_requires_auditable_model_state_digest() -> None:
    payload = _prediction()
    payload["state_digest"] = "not-a-digest"

    with pytest.raises(InferenceContractError, match="model-owned state metadata"):
        parse_model_prediction(payload)
