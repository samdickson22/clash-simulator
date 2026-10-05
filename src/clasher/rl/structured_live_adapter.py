"""Current-frame-only adapter for structured Clasher policy inference.

The adapter accepts only :class:`PublicVisionFrame`.  It builds confidence-aware
actor tensors, constructs the public legal-action mask itself, and owns every
piece of temporal policy state.  It deliberately does not import the battle
simulator, structured simulator observations, critic payloads, expert labels,
or accumulated opponent history. Confirmed own control history may be supplied
explicitly; command submissions never become acceptance evidence.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
import torch
from numpy.typing import NDArray
from torch import Tensor

from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS
from .live_inference_contract import (
    InferenceContractError,
    PublicVisionFrame,
    VisionEntity,
    validate_public_vision_frame,
)
from .public_action_mask import (
    PUBLIC_ACTION_MASK_CONTRACT_VERSION,
    PublicActionMaskBuilder,
    PublicActionMaskInput,
)

LIVE_ADAPTER_STATE_SCHEMA = "clasher.structured_live_adapter_state.v1"
ENTITY_FEATURE_SIZE = 32
GLOBAL_FEATURE_SIZE = 18
VISIBLE_CARD_SLOTS = NUM_HAND_SLOTS + 1
_KIND_INDEX = {
    "troop": 4,
    "building": 5,
    "projectile": 6,
    "area_effect": 7,
}


class LiveAdapterError(RuntimeError):
    """Base class for fail-closed live adapter errors."""


class LiveCadenceError(LiveAdapterError):
    """Raised when missing frames make recurrent time unsafe to advance."""


class _LivePolicy(Protocol):
    config: Any
    actor_encoder: Any

    def parameters(self) -> Any: ...

    def initial_state(
        self, batch_size: int, *, device: torch.device | str | None = None
    ) -> tuple[Tensor, Tensor]: ...

    def act(
        self,
        inputs: Any,
        state: tuple[Tensor, Tensor] | None = None,
        *,
        deterministic: bool = False,
    ) -> tuple[Tensor, Tensor, Tensor, tuple[Tensor, Tensor], Any]: ...


@dataclass
class LivePolicyInputs:
    """Duck-typed equivalent of PolicyInputs without importing model.py."""

    entity_ids: Tensor
    entity_features: Tensor
    entity_mask: Tensor
    hand_ids: Tensor
    global_features: Tensor
    action_mask: Tensor
    previous_actions: Tensor
    previous_rewards: Tensor
    episode_starts: Tensor
    entity_id_confidence: Tensor | None = None
    entity_feature_confidence: Tensor | None = None
    hand_id_confidence: Tensor | None = None
    global_feature_confidence: Tensor | None = None
    critic_entity_ids: Tensor | None = None
    critic_entity_features: Tensor | None = None
    critic_entity_mask: Tensor | None = None
    critic_card_ids: Tensor | None = None
    critic_global_features: Tensor | None = None
    opponent_history_ids: Tensor | None = None
    opponent_history_ages: Tensor | None = None
    opponent_seen_card_ids: Tensor | None = None
    opponent_play_event_ids: Tensor | None = None
    opponent_play_event_confidence: Tensor | None = None
    own_last_play_ids: Tensor | None = None
    own_last_play_features: Tensor | None = None
    entity_levels: Tensor | None = None
    entity_level_confidence: Tensor | None = None
    hand_levels: Tensor | None = None
    hand_level_confidence: Tensor | None = None

    @property
    def batch_size(self) -> int:
        return int(self.entity_ids.shape[0])

    @property
    def sequence_length(self) -> int:
        return int(self.entity_ids.shape[1])


@dataclass(frozen=True)
class PreparedLiveStep:
    inputs: LivePolicyInputs
    action_mask: NDArray[np.bool_]
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class SerializedLiveAdapterState:
    payload: bytes
    sha256: str


@dataclass(frozen=True)
class LiveDecision:
    episode_id: str
    frame_id: str
    disposition: str
    action: int | None
    action_mask: NDArray[np.bool_] | None
    state_step: int
    state: SerializedLiveAdapterState
    diagnostics: dict[str, Any]


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _tensor(
    value: NDArray[Any], dtype: torch.dtype, device: torch.device
) -> Tensor:
    return torch.as_tensor(value, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)


class StructuredLiveInferenceAdapter:
    """Own recurrent inference for one actor and one explicitly reset episode."""

    def __init__(
        self,
        *,
        model: _LivePolicy,
        token_names: tuple[str, ...] | list[str],
        public_action_mask_builder: PublicActionMaskBuilder,
        actor_id: int,
        cadence_ms: int = 400,
        maximum_gap_intervals: int = 2,
        deterministic: bool = True,
        device: torch.device | str | None = None,
    ) -> None:
        if actor_id not in {0, 1}:
            raise ValueError("actor_id must be 0 or 1")
        if cadence_ms <= 0 or maximum_gap_intervals < 1:
            raise ValueError("cadence and maximum gap must be positive")
        config = model.config
        if str(getattr(config, "actor_observation_domain", "")) not in {
            "causal-frame-v1",
            "causal-vision-v1",
        }:
            raise ValueError("live adapter requires a causal actor checkpoint")
        if not bool(getattr(config, "public_observation_confidence", False)):
            raise ValueError("live adapter requires confidence-aware actor inputs")
        if int(getattr(config, "entity_feature_size", -1)) != ENTITY_FEATURE_SIZE:
            raise ValueError("live adapter requires the 32-feature entity schema")
        if int(getattr(config, "actor_global_size", -1)) != GLOBAL_FEATURE_SIZE:
            raise ValueError("live adapter requires the 18-feature global schema")
        if int(getattr(config, "public_history_slots", 0)) != 0 or int(
            getattr(config, "public_seen_card_slots", 0)
        ) != 0:
            raise ValueError(
                "live adapter refuses externally accumulated opponent history"
            )
        names = tuple(str(name) for name in token_names)
        if len(names) != int(getattr(config, "num_tokens", -1)):
            raise ValueError("token names do not match checkpoint configuration")
        if len(names) < 2 or names[:2] != ("<pad>", "<unknown>"):
            raise ValueError("token names must start with pad and unknown")
        self.model = model
        self.token_names = names
        self.public_action_mask_builder = public_action_mask_builder
        if tuple(public_action_mask_builder.builder.token_names) != names:
            raise ValueError("public mask builder vocabulary does not match checkpoint")
        self.actor_id = actor_id
        self._canonical_lane_globals = bool(
            getattr(config, "canonical_lane_globals", False)
        )
        self.cadence_ms = int(cadence_ms)
        self.maximum_gap_intervals = int(maximum_gap_intervals)
        self.deterministic = bool(deterministic)
        if device is None:
            try:
                device = next(model.parameters()).device
            except StopIteration as exc:
                raise ValueError("model has no parameters; provide a device") from exc
        self.device = torch.device(device)
        self._direct_tokens = {name: index for index, name in enumerate(names)}
        normalized: dict[str, list[int]] = {}
        for index, name in enumerate(names):
            normalized.setdefault(_normalized_name(name), []).append(index)
        self._normalized_tokens = {
            name: indices[0] for name, indices in normalized.items() if len(indices) == 1
        }
        self._static_features: NDArray[np.float32] | None = None
        static = getattr(model.actor_encoder, "card_stat_features", None)
        if isinstance(static, Tensor) and static.ndim == 2 and static.shape[1] >= 16:
            self._static_features = (
                static.detach().to(device="cpu", dtype=torch.float32).numpy().copy()
            )
        self._episode_id: str | None = None
        self._state: tuple[Tensor, Tensor] | None = None
        self._previous_action = self.public_action_mask_builder.no_op_action
        self._state_step = 0
        self._last_seen_timestamp_ms: int | None = None
        self._last_decision_timestamp_ms: int | None = None
        self._last_frame_id: str | None = None
        self._seen_frame_ids: set[str] = set()
        self._requires_reset = False

    def _token_id(self, card: str, *, namespace: str = "card_action") -> int:
        # The observation builder owns contextual current-client resolution.
        # Calling it here keeps simulator, live vision, and public-mask token
        # semantics identical for both legacy bare names and typed stable keys.
        return int(
            self.public_action_mask_builder.builder.token_id(
                card,
                namespace=namespace,
            )
        )

    def reset(self, episode_id: str) -> SerializedLiveAdapterState:
        if not episode_id:
            raise ValueError("episode_id must be nonempty")
        self._episode_id = str(episode_id)
        self._state = self.model.initial_state(1, device=self.device)
        self._previous_action = self.public_action_mask_builder.no_op_action
        self._state_step = 0
        self._last_seen_timestamp_ms = None
        self._last_decision_timestamp_ms = None
        self._last_frame_id = None
        self._seen_frame_ids.clear()
        self._requires_reset = False
        return self.serialize_state()

    def _canonical_position(self, x: float, y: float) -> tuple[float, float]:
        if self.actor_id == 1:
            return BOARD_WIDTH - x, BOARD_HEIGHT - y
        return x, y

    def _entity_rows(
        self, frame: PublicVisionFrame
    ) -> tuple[
        NDArray[np.int64],
        NDArray[np.float32],
        NDArray[np.bool_],
        NDArray[np.float32],
        NDArray[np.float32],
        NDArray[np.int64],
        NDArray[np.float32],
        dict[str, Any],
    ]:
        max_entities = int(self.model.config.max_entities)
        rows: list[
            tuple[tuple[Any, ...], int, NDArray[np.float32], NDArray[np.float32], float, int, float]
        ] = []
        unknown_entities: list[str] = []
        ignored_statuses = 0
        for entity in frame.entities:
            if not (0.0 <= entity.x_tiles <= BOARD_WIDTH) or not (
                0.0 <= entity.y_tiles <= BOARD_HEIGHT
            ):
                raise InferenceContractError(
                    f"entity {entity.track_id} position is outside the arena"
                )
            kind_index = _KIND_INDEX.get(entity.kind)
            if kind_index is None:
                unknown_entities.append(entity.track_id)
                continue
            normalized_card = _normalized_name(entity.card)
            namespace = (
                "tower"
                if normalized_card in {"tower", "kingtower"}
                else {
                    "troop": "troop_body",
                    "building": "building_body",
                    "projectile": "projectile",
                    "area_effect": "area_effect",
                }[entity.kind]
            )
            token_id = self._token_id(entity.card, namespace=namespace)
            if token_id <= 1:
                unknown_entities.append(entity.track_id)
                continue
            x, y = self._canonical_position(entity.x_tiles, entity.y_tiles)
            row = np.zeros((ENTITY_FEATURE_SIZE,), dtype=np.float32)
            confidence = np.zeros((ENTITY_FEATURE_SIZE,), dtype=np.float32)
            row[0] = x / BOARD_WIDTH
            row[1] = y / BOARD_HEIGHT
            confidence[0:2] = entity.confidence
            own = entity.player_id == self.actor_id
            row[2] = float(own)
            row[3] = float(not own)
            confidence[2:4] = entity.confidence
            row[kind_index] = 1.0
            confidence[4:9] = entity.confidence
            if entity.hp_fraction is not None:
                row[9] = entity.hp_fraction
                confidence[9] = entity.hp_confidence
            # Only static channels with exactly matching packaged semantics are
            # reconstructed. Speed is deliberately absent: the model's card
            # table stores a different normalization from entity row 23.
            if self._static_features is not None:
                static = self._static_features[token_id]
                row[24] = static[7]
                row[25] = static[8]
                row[26] = static[12]
                row[30] = static[6]
                confidence[[24, 25, 26, 30]] = entity.confidence
            ignored_statuses += len(entity.statuses)
            sort_key = (
                kind_index,
                int(not own),
                token_id,
                round(float(row[1]), 5),
                round(float(row[0]), 5),
                entity.track_id,
            )
            rows.append((sort_key, token_id, row, confidence, entity.confidence, entity.level or 0, entity.level_confidence))
        rows.sort(key=lambda item: item[0])
        if len(rows) > max_entities:
            raise InferenceContractError(
                f"visible entities exceed checkpoint capacity {max_entities}"
            )
        entity_ids = np.zeros((max_entities,), dtype=np.int64)
        entity_features = np.zeros((max_entities, ENTITY_FEATURE_SIZE), dtype=np.float32)
        entity_mask = np.zeros((max_entities,), dtype=np.bool_)
        identity_confidence = np.zeros((max_entities,), dtype=np.float32)
        feature_confidence = np.zeros(
            (max_entities, ENTITY_FEATURE_SIZE), dtype=np.float32
        )
        entity_levels = np.zeros(max_entities, dtype=np.int64)
        entity_level_confidence = np.zeros(max_entities, dtype=np.float32)
        for index, (_, token_id, row, confidence, id_confidence, level, level_confidence) in enumerate(rows):
            entity_levels[index] = level
            entity_level_confidence[index] = level_confidence
            entity_ids[index] = token_id
            entity_features[index] = row
            entity_mask[index] = True
            identity_confidence[index] = id_confidence
            feature_confidence[index] = confidence
        return (
            entity_ids,
            entity_features,
            entity_mask,
            identity_confidence,
            feature_confidence,
            entity_levels,
            entity_level_confidence,
            {
                "unknown_entity_track_ids": unknown_entities,
                "ignored_visible_status_count": ignored_statuses,
                "motion_channels": "zero_current_frame_only",
                "base_speed_channel": "zero_incompatible_packaged_normalization",
                "identity_confidence_use": "broadcast_to_identity_position_team_kind",
                "hp_confidence_use": "separate_visible_bar_measurement",
            },
        )

    def _hand(
        self, frame: PublicVisionFrame
    ) -> tuple[NDArray[np.int64], NDArray[np.float32], dict[str, Any]]:
        ids = np.zeros((VISIBLE_CARD_SLOTS,), dtype=np.int64)
        confidence = np.zeros((VISIBLE_CARD_SLOTS,), dtype=np.float32)
        unknown: list[int] = []
        for index, (card, card_confidence) in enumerate(
            zip(frame.own_hand, frame.own_hand_confidence, strict=True)
        ):
            token_id = self._token_id(card)
            if token_id <= 1:
                unknown.append(index)
                continue
            ids[index] = token_id
            confidence[index] = card_confidence
        if frame.own_next_card is not None:
            token_id = self._token_id(frame.own_next_card)
            if token_id > 1:
                ids[NUM_HAND_SLOTS] = token_id
                confidence[NUM_HAND_SLOTS] = frame.own_next_card_confidence
            else:
                unknown.append(NUM_HAND_SLOTS)
        return ids, confidence, {
            "current_hand_complete": len(frame.own_hand) == NUM_HAND_SLOTS
            and not any(index < NUM_HAND_SLOTS for index in unknown),
            "next_card_observed": bool(ids[NUM_HAND_SLOTS] > 0),
            "unknown_hand_slots": unknown,
        }

    @staticmethod
    def _is_king_tower(entity: VisionEntity) -> bool:
        return _normalized_name(entity.card) == "kingtower"

    @staticmethod
    def _is_princess_tower(entity: VisionEntity) -> bool:
        return _normalized_name(entity.card) in {
            "tower",
            "queentower",
            "cannoneertower",
            "daggerduchesstower",
        }

    def _globals(
        self, frame: PublicVisionFrame
    ) -> tuple[NDArray[np.float32], NDArray[np.float32], dict[str, Any]]:
        values = np.zeros((GLOBAL_FEATURE_SIZE,), dtype=np.float32)
        confidence = np.zeros((GLOBAL_FEATURE_SIZE,), dtype=np.float32)
        if frame.visible_clock_seconds is not None:
            if not 0.0 <= frame.visible_clock_seconds <= 600.0:
                raise InferenceContractError("visible elapsed clock must be in [0, 600]")
            progress = min(1.0, frame.visible_clock_seconds / 300.0)
            values[0] = progress
            values[1] = 1.0 - progress
            confidence[0:2] = frame.clock_confidence
        if frame.own_elixir is not None:
            if not 0.0 <= frame.own_elixir <= 10.0:
                raise InferenceContractError("own elixir must be in [0, 10]")
            values[5] = frame.own_elixir / 10.0
            confidence[5] = frame.own_elixir_confidence
        observed_towers: list[int] = []
        for entity in frame.entities:
            if entity.hp_fraction is None or entity.kind != "building":
                continue
            own = entity.player_id == self.actor_id
            # Entity rows are always half-turn canonicalized.  Tower lane
            # globals, however, must preserve the checkpoint's explicit lane
            # contract: legacy checkpoints kept actor-1 physical left/right,
            # while fresh causal checkpoints swap lanes into actor space.
            if self.actor_id == 1 and not self._canonical_lane_globals:
                x = entity.x_tiles
            else:
                x, _ = self._canonical_position(entity.x_tiles, entity.y_tiles)
            if self._is_king_tower(entity):
                feature = 10 if own else 13
            elif self._is_princess_tower(entity):
                feature = (8 if x < BOARD_WIDTH / 2 else 9) if own else (
                    11 if x < BOARD_WIDTH / 2 else 12
                )
            else:
                continue
            if entity.hp_confidence >= confidence[feature]:
                values[feature] = entity.hp_fraction
                confidence[feature] = entity.hp_confidence
                observed_towers.append(feature)
        return values, confidence, {
            "clock_semantics": "elapsed_seconds_since_match_start",
            "checkpoint_clock_use": (
                "public_clock_model_input"
                if bool(
                    getattr(
                        self.model.config,
                        "structured_deterministic_resource_enabled",
                        False,
                    )
                )
                else "ignored_by_accepted_model_owned_decision_clock"
            ),
            "phase_globals": "zero_not_fabricated",
            "observed_tower_global_indices": sorted(set(observed_towers)),
            "unsupported_global_indices_zero": [2, 3, 4, 6, 7, 14, 15, 16, 17],
        }

    def _current_opponent_event(
        self, frame: PublicVisionFrame
    ) -> tuple[int, float, dict[str, Any]]:
        events = [event for event in frame.play_events if event.player_id != self.actor_id]
        config_uses_events = bool(
            getattr(self.model.config, "structured_deterministic_resource_enabled", False)
        )
        if len(events) != 1:
            return 0, 0.0, {
                "opponent_events_seen": len(events),
                "opponent_event_use": "ambiguous_zero" if events else "none",
                "checkpoint_consumes_events": config_uses_events,
            }
        token_id = self._token_id(events[0].card)
        if token_id <= 0:
            token_id = 1
        return token_id, events[0].confidence, {
            "opponent_events_seen": 1,
            "opponent_event_use": "model_input" if config_uses_events else "ignored_by_checkpoint",
            "checkpoint_consumes_events": config_uses_events,
        }

    def prepare_current_frame(self, frame: PublicVisionFrame) -> PreparedLiveStep:
        """Build label-free actor inputs without advancing recurrent state."""

        validate_public_vision_frame(frame)
        if self._episode_id is None or self._state is None:
            raise LiveAdapterError("adapter must be reset before inference")
        if frame.episode_id != self._episode_id:
            raise LiveAdapterError("episode changed without an explicit reset")
        (
            entity_ids,
            entity_features,
            entity_mask,
            entity_id_confidence,
            entity_feature_confidence,
            entity_levels,
            entity_level_confidence,
            entity_diagnostics,
        ) = self._entity_rows(frame)
        hand_ids, hand_confidence, hand_diagnostics = self._hand(frame)
        global_features, global_confidence, global_diagnostics = self._globals(frame)
        opponent_event_id, opponent_event_confidence, event_diagnostics = (
            self._current_opponent_event(frame)
        )
        mask_input = PublicActionMaskInput(
            entity_ids=entity_ids,
            entity_features=entity_features,
            entity_mask=entity_mask,
            hand_ids=hand_ids,
            global_features=global_features,
            entity_id_confidence=entity_id_confidence,
            hand_id_confidence=hand_confidence,
            global_feature_confidence=global_confidence,
            own_last_play=frame.own_last_play,
            board_rotated=self.actor_id == 1,
        )
        action_mask = self.public_action_mask_builder.build(mask_input)
        if action_mask.shape != (self.public_action_mask_builder.num_actions,):
            raise LiveAdapterError("public action-mask builder returned wrong shape")
        if not action_mask[self.public_action_mask_builder.no_op_action]:
            raise LiveAdapterError("public action mask must retain no-op")
        contract_version = int(getattr(self.model.config, "public_contract_version", 1))
        hand_levels = np.asarray([level or 0 for level in frame.own_card_levels], dtype=np.int64)
        hand_level_confidence = np.asarray(frame.own_card_level_confidence, dtype=np.float32)
        hand_levels[hand_ids == 0] = 0
        hand_level_confidence[hand_ids == 0] = 0
        own_play_id = 0 if frame.own_last_play is None else self._token_id(frame.own_last_play.card_name)
        own_play_known = frame.own_last_play is not None and own_play_id > 1
        own_play_features = np.asarray([float(own_play_known), frame.own_last_play.elixir_cost / 10 if own_play_known else 0], dtype=np.float32)
        inputs = LivePolicyInputs(
            own_last_play_ids=torch.as_tensor([[own_play_id if own_play_known else 0]], dtype=torch.long, device=self.device) if contract_version >= 2 else None,
            own_last_play_features=_tensor(own_play_features, torch.float32, self.device) if contract_version >= 2 else None,
            entity_levels=_tensor(entity_levels, torch.long, self.device) if contract_version >= 3 else None,
            entity_level_confidence=_tensor(entity_level_confidence, torch.float32, self.device) if contract_version >= 3 else None,
            hand_levels=_tensor(hand_levels, torch.long, self.device) if contract_version >= 4 else None,
            hand_level_confidence=_tensor(hand_level_confidence, torch.float32, self.device) if contract_version >= 4 else None,
            entity_ids=_tensor(entity_ids, torch.long, self.device),
            entity_features=_tensor(entity_features, torch.float32, self.device),
            entity_mask=_tensor(entity_mask, torch.bool, self.device),
            hand_ids=_tensor(hand_ids, torch.long, self.device),
            global_features=_tensor(global_features, torch.float32, self.device),
            action_mask=_tensor(action_mask, torch.bool, self.device),
            previous_actions=torch.as_tensor(
                [[self._previous_action]], dtype=torch.long, device=self.device
            ),
            previous_rewards=torch.zeros((1, 1), dtype=torch.float32, device=self.device),
            episode_starts=torch.as_tensor(
                [[self._state_step == 0]], dtype=torch.bool, device=self.device
            ),
            entity_id_confidence=_tensor(
                entity_id_confidence, torch.float32, self.device
            ),
            entity_feature_confidence=_tensor(
                entity_feature_confidence, torch.float32, self.device
            ),
            hand_id_confidence=_tensor(hand_confidence, torch.float32, self.device),
            global_feature_confidence=_tensor(
                global_confidence, torch.float32, self.device
            ),
            opponent_history_ids=torch.zeros(
                (1, 1, 0), dtype=torch.long, device=self.device
            ),
            opponent_history_ages=torch.zeros(
                (1, 1, 0), dtype=torch.float32, device=self.device
            ),
            opponent_seen_card_ids=torch.zeros(
                (1, 1, 0), dtype=torch.long, device=self.device
            ),
            opponent_play_event_ids=torch.as_tensor(
                [[opponent_event_id]], dtype=torch.long, device=self.device
            ),
            opponent_play_event_confidence=torch.as_tensor(
                [[opponent_event_confidence]], dtype=torch.float32, device=self.device
            ),
        )
        diagnostics = {
            "actor_id": self.actor_id,
            "canonical_perspective": True,
            "canonical_lane_globals": self._canonical_lane_globals,
            "public_action_mask_contract_version": PUBLIC_ACTION_MASK_CONTRACT_VERSION,
            "legal_actions": int(np.count_nonzero(action_mask)),
            "mask_source": "PublicActionMaskBuilder_current_public_frame",
            "critic_inputs": "absent",
            "previous_reward": "forced_zero",
            "match_lifecycle": "unknown_wait_only",
            "own_accepted_play": "confirmed" if own_play_known else "unknown",
            "levels": "measured_only_no_default_inference",
            **entity_diagnostics,
            **hand_diagnostics,
            **global_diagnostics,
            **event_diagnostics,
        }
        return PreparedLiveStep(
            inputs=inputs,
            action_mask=action_mask.astype(np.bool_, copy=True),
            diagnostics=diagnostics,
        )

    def _ignored_decision(
        self, frame: PublicVisionFrame, disposition: str, **diagnostics: Any
    ) -> LiveDecision:
        snapshot = self.serialize_state()
        return LiveDecision(
            episode_id=frame.episode_id,
            frame_id=frame.frame_id,
            disposition=disposition,
            action=None,
            action_mask=None,
            state_step=self._state_step,
            state=snapshot,
            diagnostics={"model_advanced": False, **diagnostics},
        )

    def step(self, frame: PublicVisionFrame) -> LiveDecision:
        validate_public_vision_frame(frame)
        if self._requires_reset:
            raise LiveAdapterError("adapter requires reset after a cadence failure")
        if self._episode_id is None or self._state is None:
            raise LiveAdapterError("adapter must be reset before inference")
        if frame.episode_id != self._episode_id:
            raise LiveAdapterError("episode changed without an explicit reset")
        if frame.frame_id in self._seen_frame_ids:
            return self._ignored_decision(frame, "duplicate_frame")
        if (
            self._last_seen_timestamp_ms is not None
            and frame.timestamp_ms <= self._last_seen_timestamp_ms
        ):
            if frame.timestamp_ms == self._last_seen_timestamp_ms:
                return self._ignored_decision(frame, "duplicate_timestamp")
            raise LiveAdapterError("frame timestamps moved backwards")
        self._seen_frame_ids.add(frame.frame_id)
        self._last_seen_timestamp_ms = frame.timestamp_ms
        self._last_frame_id = frame.frame_id
        if self._last_decision_timestamp_ms is not None:
            elapsed = frame.timestamp_ms - self._last_decision_timestamp_ms
            if elapsed < self.cadence_ms:
                return self._ignored_decision(
                    frame,
                    "before_cadence",
                    elapsed_since_decision_ms=elapsed,
                )
            maximum_gap = self.cadence_ms * self.maximum_gap_intervals
            if elapsed > maximum_gap:
                self._requires_reset = True
                raise LiveCadenceError(
                    f"frame gap {elapsed}ms exceeds safe maximum {maximum_gap}ms"
                )
        prepared = self.prepare_current_frame(frame)
        actions, _, _, next_state, output = self.model.act(
            prepared.inputs,
            self._state,
            deterministic=self.deterministic,
        )
        action = int(actions[0, 0].item())
        if not 0 <= action < prepared.action_mask.size or not prepared.action_mask[action]:
            raise LiveAdapterError("policy selected an action outside the public mask")
        self._state = (next_state[0].detach(), next_state[1].detach())
        self._previous_action = action
        self._state_step += 1
        self._last_decision_timestamp_ms = frame.timestamp_ms
        snapshot = self.serialize_state()
        opponent_elixir = getattr(output, "opponent_elixir", None)
        predicted_elixir = (
            None
            if opponent_elixir is None
            else float(opponent_elixir[0, 0].detach().cpu().item() * 10.0)
        )
        return LiveDecision(
            episode_id=frame.episode_id,
            frame_id=frame.frame_id,
            disposition="accepted",
            action=action,
            action_mask=prepared.action_mask,
            state_step=self._state_step,
            state=snapshot,
            diagnostics={
                "model_advanced": True,
                "selected_action_is_publicly_legal": True,
                "predicted_opponent_elixir": predicted_elixir,
                **prepared.diagnostics,
            },
        )

    @staticmethod
    def _encode_tensor(tensor: Tensor) -> dict[str, Any]:
        array = tensor.detach().to("cpu").contiguous().numpy()
        return {
            "dtype": array.dtype.str,
            "shape": list(array.shape),
            "data": base64.b64encode(array.tobytes(order="C")).decode("ascii"),
        }

    def serialize_state(self) -> SerializedLiveAdapterState:
        if self._episode_id is None or self._state is None:
            raise LiveAdapterError("adapter has no state; call reset first")
        record = {
            "schema": LIVE_ADAPTER_STATE_SCHEMA,
            "actor_id": self.actor_id,
            "episode_id": self._episode_id,
            "previous_action": self._previous_action,
            "state_step": self._state_step,
            "last_seen_timestamp_ms": self._last_seen_timestamp_ms,
            "last_decision_timestamp_ms": self._last_decision_timestamp_ms,
            "last_frame_id": self._last_frame_id,
            "seen_frame_ids": sorted(self._seen_frame_ids),
            "requires_reset": self._requires_reset,
            "hidden": self._encode_tensor(self._state[0]),
            "cell": self._encode_tensor(self._state[1]),
        }
        payload = json.dumps(
            record, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return SerializedLiveAdapterState(
            payload=payload,
            sha256=hashlib.sha256(payload).hexdigest(),
        )

    def _decode_tensor(self, record: Any, name: str) -> Tensor:
        if not isinstance(record, dict) or set(record) != {"dtype", "shape", "data"}:
            raise LiveAdapterError(f"serialized {name} tensor is malformed")
        dtype = np.dtype(str(record["dtype"]))
        if dtype.kind != "f":
            raise LiveAdapterError(f"serialized {name} tensor must be floating point")
        shape = tuple(int(value) for value in record["shape"])
        raw = base64.b64decode(str(record["data"]), validate=True)
        expected_bytes = math.prod(shape) * dtype.itemsize
        if len(raw) != expected_bytes:
            raise LiveAdapterError(f"serialized {name} tensor byte count changed")
        array = np.frombuffer(raw, dtype=dtype).reshape(shape).copy()
        return torch.as_tensor(array, device=self.device)

    def restore_state(self, snapshot: SerializedLiveAdapterState) -> None:
        if hashlib.sha256(snapshot.payload).hexdigest() != snapshot.sha256:
            raise LiveAdapterError("serialized adapter state digest changed")
        try:
            record = json.loads(snapshot.payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LiveAdapterError("serialized adapter state is not valid JSON") from exc
        if not isinstance(record, dict) or record.get("schema") != LIVE_ADAPTER_STATE_SCHEMA:
            raise LiveAdapterError("unsupported serialized adapter state schema")
        if int(record.get("actor_id", -1)) != self.actor_id:
            raise LiveAdapterError("serialized adapter perspective changed")
        hidden = self._decode_tensor(record.get("hidden"), "hidden")
        cell = self._decode_tensor(record.get("cell"), "cell")
        expected = self.model.initial_state(1, device=self.device)
        if hidden.shape != expected[0].shape or cell.shape != expected[1].shape:
            raise LiveAdapterError("serialized policy state shape changed")
        self._episode_id = str(record["episode_id"])
        self._state = (hidden, cell)
        self._previous_action = int(record["previous_action"])
        self._state_step = int(record["state_step"])
        self._last_seen_timestamp_ms = record["last_seen_timestamp_ms"]
        self._last_decision_timestamp_ms = record["last_decision_timestamp_ms"]
        self._last_frame_id = record["last_frame_id"]
        self._seen_frame_ids = {str(value) for value in record["seen_frame_ids"]}
        self._requires_reset = bool(record["requires_reset"])
