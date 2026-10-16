"""Fail-closed contract and metrics for live, vision-only policy inference.

The evaluator deliberately has no dependency on :mod:`clasher.battle`.  A live
adapter receives one current public frame at a time and owns all recurrent
state behind its ``step`` method.  Held-out labels are loaded and scored only
after inference has completed, so they cannot become policy inputs by accident.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from .own_card_history import AcceptedOwnPlay

LIVE_VISION_SCHEMA_VERSION = 1
LIVE_PREDICTION_SCHEMA_VERSION = 1
LIVE_LABEL_SCHEMA_VERSION = 1

HELD_OUT_SPLITS = frozenset({"validation", "heldout", "archetype_test", "chronology_test"})
PUBLIC_STATUSES = frozenset(
    {
        "charging",
        "frozen",
        "healing",
        "hidden",
        "poisoned",
        "raged",
        "revealed",
        "shielded",
        "slowed",
        "stunned",
    }
)
PUBLIC_ENTITY_KINDS = frozenset(
    {"troop", "building", "projectile", "area_effect"}
)

# These names denote privileged simulator state rather than a measurement made
# from the current client frame.  Normalization also catches camelCase keys.
_FORBIDDEN_INPUT_KEYS = frozenset(
    {
        "action_mask",
        "action_masks",
        "affordable_actions",
        "attack_windup",
        "battle",
        "battle_state",
        "champion_cooldown",
        "critic",
        "critic_state",
        "deployment_remaining",
        "engine_id",
        "exact_hp",
        "exact_opponent_elixir",
        "expert_action",
        "expert_actions",
        "game_tick",
        "haste_remaining",
        "internal_tick",
        "legal_action_mask",
        "labels",
        "next_card_refill",
        "object_id",
        "opponent_cycle",
        "opponent_deck",
        "opponent_elixir",
        "opponent_hand",
        "opponent_history",
        "opponent_history_ages",
        "opponent_history_ids",
        "opponent_next_card",
        "opponent_seen_card_ids",
        "pending_damage",
        "public_card_play_history",
        "rng_state",
        "simulator_state",
        "slow_remaining",
        "stun_remaining",
        "target_id",
    }
)


class InferenceContractError(ValueError):
    """Raised when data crosses the live inference boundary illegally."""


def _snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).replace("-", "_").lower()


def _finite(name: str, value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise InferenceContractError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise InferenceContractError(f"{name} must be finite")
    return result


def _unit(name: str, value: object) -> float:
    result = _finite(name, value)
    if not 0.0 <= result <= 1.0:
        raise InferenceContractError(f"{name} must be in [0, 1]")
    return result


def _strict_keys(payload: Mapping[str, Any], allowed: set[str], path: str) -> None:
    extras = sorted(set(payload) - allowed)
    if extras:
        raise InferenceContractError(f"{path} has unsupported keys: {extras}")


def _require_keys(payload: Mapping[str, Any], required: set[str], path: str) -> None:
    missing = sorted(required - set(payload))
    if missing:
        raise InferenceContractError(f"{path} is missing required keys: {missing}")


def _optional_number(
    name: str, value: object, confidence_value: object
) -> tuple[float | None, float]:
    confidence = _unit(f"{name} confidence", confidence_value)
    if value is None:
        if confidence != 0.0:
            raise InferenceContractError(f"{name} is missing but has confidence")
        return None, confidence
    if confidence <= 0.0:
        raise InferenceContractError(f"{name} fabricates a zero-confidence value")
    return _finite(name, value), confidence


def assert_no_privileged_payload(value: object, *, path: str = "input") -> None:
    """Reject simulator objects and privileged keys before schema parsing."""

    value_type = type(value)
    qualified = f"{value_type.__module__}.{value_type.__qualname__}"
    if value_type.__name__ == "BattleState" or qualified == "clasher.battle.BattleState":
        raise InferenceContractError(f"{path} contains BattleState")
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            if not isinstance(raw_key, str):
                raise InferenceContractError(f"{path} contains a non-string key")
            key = _snake_case(raw_key)
            if key in _FORBIDDEN_INPUT_KEYS or key.startswith("critic_"):
                raise InferenceContractError(f"{path}.{raw_key} is privileged")
            assert_no_privileged_payload(child, path=f"{path}.{raw_key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_no_privileged_payload(child, path=f"{path}[{index}]")
        return
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    raise InferenceContractError(
        f"{path} contains non-JSON value of type {qualified}"
    )


@dataclass(frozen=True)
class VisionEntity:
    track_id: str
    card: str
    kind: str
    player_id: int
    x_tiles: float
    y_tiles: float
    confidence: float
    hp_fraction: float | None = None
    hp_confidence: float = 0.0
    statuses: tuple[str, ...] = ()
    level: int | None = None
    level_confidence: float = 0.0


@dataclass(frozen=True)
class PublicPlayEvent:
    event_id: str
    player_id: int
    card: str
    confidence: float
    x_tiles: float | None = None
    y_tiles: float | None = None


@dataclass(frozen=True)
class PublicVisionFrame:
    """Current public measurements and optional confirmed own control metadata.

    There is no accumulated opponent history. Omitted levels and own accepted
    play remain unknown; a submitted command is not an accepted-play source.
    """

    episode_id: str
    frame_id: str
    timestamp_ms: int
    visible_clock_seconds: float | None
    clock_confidence: float
    own_elixir: float | None
    own_elixir_confidence: float
    own_hand: tuple[str, ...]
    own_hand_confidence: tuple[float, ...]
    own_next_card: str | None
    own_next_card_confidence: float
    entities: tuple[VisionEntity, ...]
    play_events: tuple[PublicPlayEvent, ...]
    # Four own hand slots and visible next, supplied only when measured.
    own_card_levels: tuple[int | None, ...] = (None,) * 5
    own_card_level_confidence: tuple[float, ...] = (0.0,) * 5
    own_last_play: AcceptedOwnPlay | None = None
    # Optional independent screen-anchor channel; older producers omit it.
    tower_observations: tuple = ()


@dataclass(frozen=True)
class PlacementPrediction:
    event_id: str
    x_tiles: float
    y_tiles: float


@dataclass(frozen=True)
class ModelPrediction:
    episode_id: str
    frame_id: str
    state_step: int
    state_digest: str
    clock_seconds: float | None
    opponent_elixir: float | None
    cycle_plays_until_available: dict[str, int]
    placements: tuple[PlacementPrediction, ...]
    entity_hp: dict[str, float]
    statuses: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class EvaluationLabels:
    split: str
    episode_id: str
    frame_id: str
    clock_seconds: float | None
    opponent_elixir: float | None
    cycle_plays_until_available: dict[str, int]
    placements: tuple[PlacementPrediction, ...]
    entity_hp: dict[str, float]
    statuses: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class EvaluationThresholds:
    minimum_samples_per_metric: int = 1
    maximum_clock_mae_seconds: float = 1.0
    maximum_elixir_mae: float = 0.5
    minimum_cycle_accuracy: float = 0.95
    minimum_placement_within_one_tile: float = 0.90
    maximum_hp_mae: float = 0.10
    minimum_status_f1: float = 0.90

    def validate(self) -> None:
        if self.minimum_samples_per_metric <= 0:
            raise ValueError("minimum_samples_per_metric must be positive")
        for name in ("maximum_clock_mae_seconds", "maximum_elixir_mae", "maximum_hp_mae"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        for name in (
            "minimum_cycle_accuracy",
            "minimum_placement_within_one_tile",
            "minimum_status_f1",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")


class LiveInferenceAdapter(Protocol):
    """A model wrapper whose recurrent state is private and model-owned."""

    def reset(self, episode_id: str) -> None: ...

    def step(self, frame: PublicVisionFrame) -> ModelPrediction: ...


def _observed_level(value: object, confidence_value: object, path: str) -> tuple[int | None, float]:
    confidence = _unit(f"{path} confidence", confidence_value)
    if value is None:
        if confidence != 0:
            raise InferenceContractError(f"{path} is missing but has confidence")
    elif type(value) is not int or not 1 <= value <= 127 or confidence <= 0:
        raise InferenceContractError(f"{path} requires integer level 1..127 and positive confidence")
    return value, confidence


def _parse_entity(payload: object, path: str) -> VisionEntity:
    if not isinstance(payload, Mapping):
        raise InferenceContractError(f"{path} must be an object")
    _strict_keys(
        payload,
        {"track_id", "card", "kind", "player_id", "x_tiles", "y_tiles", "confidence", "hp_fraction", "hp_confidence", "statuses", "level", "level_confidence"},
        path,
    )
    statuses = tuple(str(value) for value in payload.get("statuses", ()))
    unknown = sorted(set(statuses) - PUBLIC_STATUSES)
    if unknown:
        raise InferenceContractError(f"{path}.statuses has unsupported values: {unknown}")
    kind = str(payload["kind"])
    if kind not in PUBLIC_ENTITY_KINDS:
        raise InferenceContractError(f"{path}.kind is unsupported: {kind}")
    hp = payload.get("hp_fraction")
    hp_confidence = _unit(f"{path}.hp_confidence", payload.get("hp_confidence", 0.0))
    if hp is None and hp_confidence != 0.0:
        raise InferenceContractError(f"{path}.hp_fraction is missing but has confidence")
    if hp is not None and hp_confidence <= 0.0:
        raise InferenceContractError(f"{path}.hp_fraction has zero confidence")
    player_id = int(payload["player_id"])
    if player_id not in {0, 1}:
        raise InferenceContractError(f"{path}.player_id must be 0 or 1")
    level, level_confidence = _observed_level(payload.get("level"), payload.get("level_confidence", 0.0), f"{path}.level")
    return VisionEntity(
        level=level,
        level_confidence=level_confidence,
        track_id=str(payload["track_id"]),
        card=str(payload["card"]),
        kind=kind,
        player_id=player_id,
        x_tiles=_finite(f"{path}.x_tiles", payload["x_tiles"]),
        y_tiles=_finite(f"{path}.y_tiles", payload["y_tiles"]),
        confidence=_unit(f"{path}.confidence", payload["confidence"]),
        hp_fraction=None if hp is None else _unit(f"{path}.hp_fraction", hp),
        hp_confidence=hp_confidence,
        statuses=statuses,
    )


def _parse_play(payload: object, path: str) -> PublicPlayEvent:
    if not isinstance(payload, Mapping):
        raise InferenceContractError(f"{path} must be an object")
    _strict_keys(payload, {"event_id", "player_id", "card", "confidence", "x_tiles", "y_tiles"}, path)
    x = payload.get("x_tiles")
    y = payload.get("y_tiles")
    if (x is None) != (y is None):
        raise InferenceContractError(f"{path} placement coordinates must appear together")
    player_id = int(payload["player_id"])
    if player_id not in {0, 1}:
        raise InferenceContractError(f"{path}.player_id must be 0 or 1")
    return PublicPlayEvent(
        event_id=str(payload["event_id"]),
        player_id=player_id,
        card=str(payload["card"]),
        confidence=_unit(f"{path}.confidence", payload["confidence"]),
        x_tiles=None if x is None else _finite(f"{path}.x_tiles", x),
        y_tiles=None if y is None else _finite(f"{path}.y_tiles", y),
    )


def parse_public_vision_frame(payload: object) -> PublicVisionFrame:
    assert_no_privileged_payload(payload)
    if not isinstance(payload, Mapping):
        raise InferenceContractError("vision frame must be an object")
    _strict_keys(payload, {"schema_version", "episode_id", "frame_id", "timestamp_ms", "public"}, "input")
    _require_keys(payload, {"schema_version", "episode_id", "frame_id", "timestamp_ms", "public"}, "input")
    if int(payload.get("schema_version", -1)) != LIVE_VISION_SCHEMA_VERSION:
        raise InferenceContractError("unsupported live vision schema")
    public = payload.get("public")
    if not isinstance(public, Mapping):
        raise InferenceContractError("input.public must be an object")
    _strict_keys(
        public,
        {
            "visible_clock_seconds",
            "clock_confidence",
            "own_elixir",
            "own_elixir_confidence",
            "own_hand",
            "own_hand_confidence",
            "own_next_card",
            "own_next_card_confidence",
            "entities",
            "play_events",
            "own_card_levels",
            "own_card_level_confidence",
            "own_last_play",
            "tower_observations",
        },
        "input.public",
    )
    _require_keys(
        public,
        {
            "visible_clock_seconds",
            "clock_confidence",
            "own_elixir",
            "own_elixir_confidence",
            "own_hand",
            "own_hand_confidence",
            "own_next_card",
            "own_next_card_confidence",
            "entities",
            "play_events",
        },
        "input.public",
    )
    clock = public.get("visible_clock_seconds")
    own_elixir = public.get("own_elixir")
    own_hand = tuple(str(card) for card in public.get("own_hand", ()))
    own_hand_confidence = tuple(
        _unit(f"own hand confidence {index}", value)
        for index, value in enumerate(public.get("own_hand_confidence", ()))
    )
    own_next_card = public.get("own_next_card")
    if len(own_hand) > 4:
        raise InferenceContractError("input.public.own_hand exposes more than four cards")
    if len(own_hand_confidence) != len(own_hand):
        raise InferenceContractError("own hand confidence must match own hand")
    visible_clock, clock_confidence = _optional_number(
        "visible clock", clock, public["clock_confidence"]
    )
    visible_own_elixir, own_elixir_confidence = _optional_number(
        "own elixir", own_elixir, public["own_elixir_confidence"]
    )
    next_confidence = _unit(
        "own next-card confidence", public["own_next_card_confidence"]
    )
    if own_next_card is None and next_confidence != 0.0:
        raise InferenceContractError("own next card is missing but has confidence")
    if own_next_card is not None and next_confidence <= 0.0:
        raise InferenceContractError("own next card fabricates a zero-confidence value")
    raw_levels = public.get("own_card_levels", (None,) * 5)
    raw_confidence = public.get("own_card_level_confidence", (0.0,) * 5)
    if not isinstance(raw_levels, (list, tuple)) or not isinstance(raw_confidence, (list, tuple)) or len(raw_levels) != 5 or len(raw_confidence) != 5:
        raise InferenceContractError("own card levels require five hand-plus-next slots")
    observed_levels = tuple(_observed_level(level, confidence, f"own card level {index}")
        for index, (level, confidence) in enumerate(zip(raw_levels, raw_confidence)))
    for index, (level, _) in enumerate(observed_levels):
        if level is not None and ((index < 4 and index >= len(own_hand)) or (index == 4 and own_next_card is None)):
            raise InferenceContractError("absent own card cannot have an observed level")
    own_last_play = None
    raw_play = public.get("own_last_play")
    if raw_play is not None:
        if not isinstance(raw_play, Mapping):
            raise InferenceContractError("own_last_play must be a confirmed play object or unknown")
        _strict_keys(raw_play, {"card_name", "elixir_cost"}, "own_last_play")
        _require_keys(raw_play, {"card_name", "elixir_cost"}, "own_last_play")
        try:
            own_last_play = AcceptedOwnPlay(raw_play["card_name"], raw_play["elixir_cost"])
        except ValueError as exc:
            raise InferenceContractError(str(exc)) from exc
    entities = tuple(
        _parse_entity(row, f"input.public.entities[{index}]")
        for index, row in enumerate(public.get("entities", ()))
    )
    plays = tuple(
        _parse_play(row, f"input.public.play_events[{index}]")
        for index, row in enumerate(public.get("play_events", ()))
    )
    for name, rows in (("track_id", entities), ("event_id", plays)):
        values = [str(getattr(row, name)) for row in rows]
        if len(values) != len(set(values)):
            raise InferenceContractError(f"input.public has duplicate {name}")
    timestamp_ms = int(payload["timestamp_ms"])
    if timestamp_ms < 0:
        raise InferenceContractError("timestamp_ms must be non-negative")
    from clasher.live.tower_channel import parse_observations
    try:
        towers = parse_observations(public.get("tower_observations", ()), timestamp_ms)
    except (TypeError, ValueError) as exc:
        raise InferenceContractError(str(exc)) from exc
    return PublicVisionFrame(
        episode_id=str(payload["episode_id"]),
        frame_id=str(payload["frame_id"]),
        timestamp_ms=timestamp_ms,
        visible_clock_seconds=visible_clock,
        clock_confidence=clock_confidence,
        own_elixir=visible_own_elixir,
        own_elixir_confidence=own_elixir_confidence,
        own_hand=own_hand,
        own_hand_confidence=own_hand_confidence,
        own_next_card=None if own_next_card is None else str(own_next_card),
        own_next_card_confidence=next_confidence,
        entities=entities,
        play_events=plays,
        own_card_levels=tuple(level for level, _ in observed_levels),
        own_card_level_confidence=tuple(confidence for _, confidence in observed_levels),
        own_last_play=own_last_play,
        tower_observations=towers,
    )


def validate_public_vision_frame(frame: PublicVisionFrame) -> None:
    """Reapply the serialized boundary to a directly constructed dataclass."""

    if not isinstance(frame, PublicVisionFrame):
        raise TypeError("live input must be PublicVisionFrame")
    payload = {
        "schema_version": LIVE_VISION_SCHEMA_VERSION,
        "episode_id": frame.episode_id,
        "frame_id": frame.frame_id,
        "timestamp_ms": frame.timestamp_ms,
        "public": {
            "visible_clock_seconds": frame.visible_clock_seconds,
            "clock_confidence": frame.clock_confidence,
            "own_elixir": frame.own_elixir,
            "own_elixir_confidence": frame.own_elixir_confidence,
            "own_hand": list(frame.own_hand),
            "own_hand_confidence": list(frame.own_hand_confidence),
            "own_next_card": frame.own_next_card,
            "own_next_card_confidence": frame.own_next_card_confidence,
            "entities": [asdict(entity) for entity in frame.entities],
            "play_events": [asdict(event) for event in frame.play_events],
            "own_card_levels": list(frame.own_card_levels),
            "own_card_level_confidence": list(frame.own_card_level_confidence),
            "own_last_play": None if frame.own_last_play is None else asdict(frame.own_last_play),
            "tower_observations": [asdict(row) for row in frame.tower_observations],
        },
    }
    reparsed = parse_public_vision_frame(payload)
    if reparsed != frame:
        raise InferenceContractError("direct public frame is not canonical")


def _parse_placements(rows: object, path: str) -> tuple[PlacementPrediction, ...]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise InferenceContractError(f"{path} must be an array")
    result: list[PlacementPrediction] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise InferenceContractError(f"{path}[{index}] must be an object")
        _strict_keys(row, {"event_id", "x_tiles", "y_tiles"}, f"{path}[{index}]")
        result.append(
            PlacementPrediction(
                event_id=str(row["event_id"]),
                x_tiles=_finite(f"{path}[{index}].x_tiles", row["x_tiles"]),
                y_tiles=_finite(f"{path}[{index}].y_tiles", row["y_tiles"]),
            )
        )
    if len({row.event_id for row in result}) != len(result):
        raise InferenceContractError(f"{path} has duplicate event ids")
    return tuple(result)


def _parse_cycle(payload: object, path: str) -> dict[str, int]:
    if not isinstance(payload, Mapping):
        raise InferenceContractError(f"{path} must be an object")
    result: dict[str, int] = {}
    for card, raw in payload.items():
        count = int(raw)
        if count < 0 or count > 4:
            raise InferenceContractError(f"{path}.{card} must be in [0, 4]")
        result[str(card)] = count
    return result


def _parse_hp(payload: object, path: str) -> dict[str, float]:
    if not isinstance(payload, Mapping):
        raise InferenceContractError(f"{path} must be an object")
    return {str(key): _unit(f"{path}.{key}", value) for key, value in payload.items()}


def _parse_statuses(payload: object, path: str) -> dict[str, tuple[str, ...]]:
    if not isinstance(payload, Mapping):
        raise InferenceContractError(f"{path} must be an object")
    result: dict[str, tuple[str, ...]] = {}
    for track_id, raw_values in payload.items():
        if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)):
            raise InferenceContractError(f"{path}.{track_id} must be an array")
        values = tuple(str(value) for value in raw_values)
        unknown = sorted(set(values) - PUBLIC_STATUSES)
        if unknown:
            raise InferenceContractError(f"{path}.{track_id} has unsupported statuses: {unknown}")
        result[str(track_id)] = values
    return result


def parse_model_prediction(payload: object) -> ModelPrediction:
    if not isinstance(payload, Mapping):
        raise InferenceContractError("prediction must be an object")
    _strict_keys(
        payload,
        {"schema_version", "episode_id", "frame_id", "state_step", "state_digest", "predictions"},
        "prediction",
    )
    _require_keys(
        payload,
        {"schema_version", "episode_id", "frame_id", "state_step", "state_digest", "predictions"},
        "prediction",
    )
    if int(payload.get("schema_version", -1)) != LIVE_PREDICTION_SCHEMA_VERSION:
        raise InferenceContractError("unsupported live prediction schema")
    predictions = payload.get("predictions")
    if not isinstance(predictions, Mapping):
        raise InferenceContractError("prediction.predictions must be an object")
    _strict_keys(
        predictions,
        {"clock_seconds", "opponent_elixir", "cycle_plays_until_available", "placements", "entity_hp", "statuses"},
        "prediction.predictions",
    )
    _require_keys(
        predictions,
        {"clock_seconds", "opponent_elixir", "cycle_plays_until_available", "placements", "entity_hp", "statuses"},
        "prediction.predictions",
    )
    state_step = int(payload["state_step"])
    digest = str(payload["state_digest"])
    if state_step < 0 or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise InferenceContractError("prediction has invalid model-owned state metadata")
    clock = predictions.get("clock_seconds")
    elixir = predictions.get("opponent_elixir")
    if elixir is not None and not 0.0 <= _finite("predicted opponent elixir", elixir) <= 10.0:
        raise InferenceContractError("predicted opponent elixir must be in [0, 10]")
    return ModelPrediction(
        episode_id=str(payload["episode_id"]),
        frame_id=str(payload["frame_id"]),
        state_step=state_step,
        state_digest=digest,
        clock_seconds=None if clock is None else _finite("predicted clock", clock),
        opponent_elixir=None if elixir is None else float(elixir),
        cycle_plays_until_available=_parse_cycle(predictions.get("cycle_plays_until_available", {}), "prediction cycle"),
        placements=_parse_placements(predictions.get("placements", ()), "prediction placements"),
        entity_hp=_parse_hp(predictions.get("entity_hp", {}), "prediction entity_hp"),
        statuses=_parse_statuses(predictions.get("statuses", {}), "prediction statuses"),
    )


def validate_model_prediction(prediction: ModelPrediction) -> None:
    """Apply the serialized prediction contract to a direct adapter result."""

    payload = {
        "schema_version": LIVE_PREDICTION_SCHEMA_VERSION,
        "episode_id": prediction.episode_id,
        "frame_id": prediction.frame_id,
        "state_step": prediction.state_step,
        "state_digest": prediction.state_digest,
        "predictions": {
            "clock_seconds": prediction.clock_seconds,
            "opponent_elixir": prediction.opponent_elixir,
            "cycle_plays_until_available": prediction.cycle_plays_until_available,
            "placements": [asdict(row) for row in prediction.placements],
            "entity_hp": prediction.entity_hp,
            "statuses": prediction.statuses,
        },
    }
    parse_model_prediction(payload)


def parse_evaluation_labels(payload: object) -> EvaluationLabels:
    if not isinstance(payload, Mapping):
        raise InferenceContractError("labels must be an object")
    _strict_keys(payload, {"schema_version", "split", "episode_id", "frame_id", "labels"}, "labels")
    _require_keys(payload, {"schema_version", "split", "episode_id", "frame_id", "labels"}, "labels")
    if int(payload.get("schema_version", -1)) != LIVE_LABEL_SCHEMA_VERSION:
        raise InferenceContractError("unsupported live label schema")
    split = str(payload["split"])
    if split not in HELD_OUT_SPLITS:
        raise InferenceContractError(f"labels split is not held out: {split}")
    labels = payload.get("labels")
    if not isinstance(labels, Mapping):
        raise InferenceContractError("labels.labels must be an object")
    _strict_keys(
        labels,
        {"clock_seconds", "opponent_elixir", "cycle_plays_until_available", "placements", "entity_hp", "statuses"},
        "labels.labels",
    )
    _require_keys(
        labels,
        {"clock_seconds", "opponent_elixir", "cycle_plays_until_available", "placements", "entity_hp", "statuses"},
        "labels.labels",
    )
    clock = labels.get("clock_seconds")
    elixir = labels.get("opponent_elixir")
    if elixir is not None and not 0.0 <= _finite("label opponent elixir", elixir) <= 10.0:
        raise InferenceContractError("label opponent elixir must be in [0, 10]")
    return EvaluationLabels(
        split=split,
        episode_id=str(payload["episode_id"]),
        frame_id=str(payload["frame_id"]),
        clock_seconds=None if clock is None else _finite("label clock", clock),
        opponent_elixir=None if elixir is None else float(elixir),
        cycle_plays_until_available=_parse_cycle(labels.get("cycle_plays_until_available", {}), "label cycle"),
        placements=_parse_placements(labels.get("placements", ()), "label placements"),
        entity_hp=_parse_hp(labels.get("entity_hp", {}), "label entity_hp"),
        statuses=_parse_statuses(labels.get("statuses", {}), "label statuses"),
    )


def load_jsonl(path: Path, parser: Any) -> list[Any]:
    rows: list[Any] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            rows.append(parser(json.loads(raw)))
        except (json.JSONDecodeError, InferenceContractError, KeyError, TypeError, ValueError) as exc:
            raise InferenceContractError(f"{path}:{line_number}: {exc}") from exc
    if not rows:
        raise InferenceContractError(f"trace is empty: {path}")
    return rows


def run_public_inference(
    adapter: LiveInferenceAdapter, frames: Sequence[PublicVisionFrame]
) -> list[ModelPrediction]:
    """Run an adapter without ever exposing labels or accumulated history."""

    predictions: list[ModelPrediction] = []
    episode: str | None = None
    expected_step = 0
    previous_timestamp = -1
    for frame in frames:
        if frame.episode_id != episode:
            adapter.reset(frame.episode_id)
            episode = frame.episode_id
            expected_step = 0
            previous_timestamp = -1
        if frame.timestamp_ms <= previous_timestamp:
            raise InferenceContractError("vision timestamps must increase within an episode")
        prediction = adapter.step(frame)
        if not isinstance(prediction, ModelPrediction):
            raise InferenceContractError("adapter must return ModelPrediction")
        validate_model_prediction(prediction)
        if prediction.episode_id != frame.episode_id or prediction.frame_id != frame.frame_id:
            raise InferenceContractError("prediction identity differs from current public frame")
        if prediction.state_step != expected_step:
            raise InferenceContractError(
                f"model state step {prediction.state_step} != expected {expected_step}"
            )
        predictions.append(prediction)
        expected_step += 1
        previous_timestamp = frame.timestamp_ms
    return predictions


def _mean(values: list[float]) -> float | None:
    return None if not values else float(sum(values) / len(values))


def _metric(count: int, **values: float | None) -> dict[str, Any]:
    return {"samples": count, **values}


def evaluate_predictions(
    predictions: Sequence[ModelPrediction],
    labels: Sequence[EvaluationLabels],
    *,
    thresholds: EvaluationThresholds | None = None,
) -> dict[str, Any]:
    """Score held-out truth after inference and apply all gates fail-closed."""

    if thresholds is None:
        thresholds = EvaluationThresholds()
    thresholds.validate()
    prediction_by_key = {(row.episode_id, row.frame_id): row for row in predictions}
    if len(prediction_by_key) != len(predictions):
        raise InferenceContractError("duplicate prediction frame identity")
    label_by_key = {(row.episode_id, row.frame_id): row for row in labels}
    if len(label_by_key) != len(labels):
        raise InferenceContractError("duplicate label frame identity")
    missing_predictions = sorted(set(label_by_key) - set(prediction_by_key))
    extra_predictions = sorted(set(prediction_by_key) - set(label_by_key))

    clock_errors: list[float] = []
    elixir_errors: list[float] = []
    cycle_correct = 0
    cycle_total = 0
    placement_errors: list[float] = []
    hp_errors: list[float] = []
    status_tp = status_fp = status_fn = 0
    status_labeled_tracks = 0
    missing_values: dict[str, int] = {
        "clock": 0,
        "elixir": 0,
        "cycle": 0,
        "placement": 0,
        "hp": 0,
        "status": 0,
    }
    extra_values: dict[str, int] = {"placement": 0, "status": 0}

    for key, label in label_by_key.items():
        prediction = prediction_by_key.get(key)
        if prediction is None:
            continue
        if label.clock_seconds is not None:
            if prediction.clock_seconds is None:
                missing_values["clock"] += 1
            else:
                clock_errors.append(abs(prediction.clock_seconds - label.clock_seconds))
        if label.opponent_elixir is not None:
            if prediction.opponent_elixir is None:
                missing_values["elixir"] += 1
            else:
                elixir_errors.append(abs(prediction.opponent_elixir - label.opponent_elixir))
        for card, expected_cycle in label.cycle_plays_until_available.items():
            actual_cycle = prediction.cycle_plays_until_available.get(card)
            if actual_cycle is None:
                missing_values["cycle"] += 1
                continue
            cycle_total += 1
            cycle_correct += int(actual_cycle == expected_cycle)
        predicted_placements = {row.event_id: row for row in prediction.placements}
        labelled_placement_ids = {row.event_id for row in label.placements}
        extra_values["placement"] += len(
            set(predicted_placements) - labelled_placement_ids
        )
        for expected_placement in label.placements:
            actual_placement = predicted_placements.get(expected_placement.event_id)
            if actual_placement is None:
                missing_values["placement"] += 1
                continue
            placement_errors.append(
                math.hypot(
                    actual_placement.x_tiles - expected_placement.x_tiles,
                    actual_placement.y_tiles - expected_placement.y_tiles,
                )
            )
        for track_id, expected_hp in label.entity_hp.items():
            actual_hp = prediction.entity_hp.get(track_id)
            if actual_hp is None:
                missing_values["hp"] += 1
            else:
                hp_errors.append(abs(actual_hp - expected_hp))
        for track_id, expected_values in label.statuses.items():
            status_labeled_tracks += 1
            actual_values = prediction.statuses.get(track_id)
            if actual_values is None:
                missing_values["status"] += 1
                actual_statuses: set[str] = set()
            else:
                actual_statuses = set(actual_values)
            expected_statuses = set(expected_values)
            status_tp += len(actual_statuses & expected_statuses)
            status_fp += len(actual_statuses - expected_statuses)
            status_fn += len(expected_statuses - actual_statuses)
        for track_id in set(prediction.statuses) - set(label.statuses):
            extra_statuses = set(prediction.statuses[track_id])
            extra_values["status"] += len(extra_statuses)
            status_fp += len(extra_statuses)

    status_denominator = 2 * status_tp + status_fp + status_fn
    status_f1 = 1.0 if status_denominator == 0 else 2 * status_tp / status_denominator
    metrics = {
        "clock": _metric(len(clock_errors), mae_seconds=_mean(clock_errors)),
        "elixir": _metric(len(elixir_errors), mae=_mean(elixir_errors)),
        "cycle": _metric(cycle_total, accuracy=None if cycle_total == 0 else cycle_correct / cycle_total),
        "placement": _metric(
            len(placement_errors),
            mean_error_tiles=_mean(placement_errors),
            within_one_tile=None if not placement_errors else sum(error <= 1.0 for error in placement_errors) / len(placement_errors),
        ),
        "hp": _metric(len(hp_errors), mae=_mean(hp_errors)),
        "status": _metric(status_labeled_tracks, f1=float(status_f1)),
    }
    gate_checks = {
        "frame_coverage": not missing_predictions and not extra_predictions,
        "no_missing_values": all(value == 0 for value in missing_values.values()),
        "no_extra_values": all(value == 0 for value in extra_values.values()),
        "clock": len(clock_errors) >= thresholds.minimum_samples_per_metric and metrics["clock"]["mae_seconds"] <= thresholds.maximum_clock_mae_seconds,
        "elixir": len(elixir_errors) >= thresholds.minimum_samples_per_metric and metrics["elixir"]["mae"] <= thresholds.maximum_elixir_mae,
        "cycle": cycle_total >= thresholds.minimum_samples_per_metric and metrics["cycle"]["accuracy"] >= thresholds.minimum_cycle_accuracy,
        "placement": len(placement_errors) >= thresholds.minimum_samples_per_metric and metrics["placement"]["within_one_tile"] >= thresholds.minimum_placement_within_one_tile,
        "hp": len(hp_errors) >= thresholds.minimum_samples_per_metric and metrics["hp"]["mae"] <= thresholds.maximum_hp_mae,
        "status": status_labeled_tracks >= thresholds.minimum_samples_per_metric and status_f1 >= thresholds.minimum_status_f1,
    }
    return {
        "schema_version": 1,
        "contract": {
            "inference_inputs": "current_public_vision_only",
            "recurrent_state": "adapter_private_model_owned",
            "labels_exposed_during_inference": False,
            "simulator_imported_by_evaluator": False,
        },
        "frames": {
            "predictions": len(predictions),
            "labels": len(labels),
            "missing_predictions": [list(key) for key in missing_predictions],
            "extra_predictions": [list(key) for key in extra_predictions],
        },
        "missing_values": missing_values,
        "extra_values": extra_values,
        "metrics": metrics,
        "thresholds": asdict(thresholds),
        "gate_checks": gate_checks,
        "passed": all(gate_checks.values()),
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
