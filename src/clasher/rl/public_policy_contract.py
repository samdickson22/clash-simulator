"""Versioned public observation storage and policy input for the new pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from .model import PolicyInputs
from .structured_obs import (
    ACTOR_GLOBAL_SIZE,
    ENTITY_FEATURE_SIZE,
    VISIBLE_CARD_SLOTS,
    ActorObservation,
    StructuredObservationBuilder,
)

ARRAY_DTYPES = {
    "board_rotated": np.dtype("int8"),
    "terminal_status": np.dtype("int8"),
    "entity_ids": np.dtype("int64"),
    "entity_features": np.dtype("float32"),
    "entity_mask": np.dtype("bool"),
    "hand_ids": np.dtype("int64"),
    "global_features": np.dtype("float32"),
    "opponent_history_ids": np.dtype("int64"),
    "opponent_history_ages": np.dtype("float32"),
    "opponent_seen_card_ids": np.dtype("int64"),
    "own_last_play_ids": np.dtype("int64"),
    "own_last_play_features": np.dtype("float32"),
}
LEVEL_DTYPES = {"entity_levels": np.dtype("int64"), "entity_level_confidence": np.dtype("float32")}

CONFIDENCE_FIELDS = (
    "entity_id_confidence",
    "entity_feature_confidence",
    "hand_id_confidence",
    "global_feature_confidence",
)


@dataclass(frozen=True)
class PublicPolicySequence:
    token_names: tuple[str, ...]
    arrays: dict[str, np.ndarray]

    def __post_init__(self):
        if self.token_names[:2] != ("<pad>", "<unknown>") or len(
            set(self.token_names)
        ) != len(self.token_names):
            raise ValueError("invalid token vocabulary")
        if not set(ARRAY_DTYPES) <= self.arrays.keys() or set(self.arrays) - set(
            ARRAY_DTYPES
        ) - set(CONFIDENCE_FIELDS) - set(LEVEL_DTYPES):
            raise ValueError("public contract fields missing or unknown")
        level_fields = set(self.arrays) & set(LEVEL_DTYPES)
        if level_fields and level_fields != set(LEVEL_DTYPES):
            raise ValueError('incomplete public entity level fields')
        if level_fields:
            levels, confidence = self.arrays['entity_levels'], self.arrays['entity_level_confidence']
            if levels.dtype != np.int64 or confidence.dtype != np.float32:
                raise ValueError('invalid public entity level dtype')
            mask = self.arrays['entity_mask']
            if levels.shape != mask.shape or confidence.shape != mask.shape:
                raise ValueError('invalid public entity level shape')
            if (not np.isfinite(confidence).all() or ((confidence < 0) | (confidence > 1)).any()
                or ((levels < 0) | (levels > 127)).any()
                or ((levels == 0) != (confidence == 0)).any()
                or ((~mask) & ((levels != 0) | (confidence != 0))).any()):
                raise ValueError('invalid public entity levels or confidence')
        confidence = set(self.arrays) & set(CONFIDENCE_FIELDS)
        if confidence and confidence != set(CONFIDENCE_FIELDS):
            raise ValueError("incomplete public confidence fields")
        counts = set()
        for name, array in self.arrays.items():
            expected = ARRAY_DTYPES.get(name, LEVEL_DTYPES.get(name, np.dtype("float32")))
            if array.dtype != expected or array.ndim < 1:
                raise ValueError(f"invalid public array {name}")
            counts.add(array.shape[0])
            if np.issubdtype(array.dtype, np.floating) and not np.isfinite(array).all():
                raise ValueError(f"non-finite public array {name}")
            if name.endswith("_ids") and (
                (array < 0).any() or (array >= len(self.token_names)).any()
            ):
                raise ValueError(f"out-of-vocabulary token in {name}")
        if len(counts) != 1 or next(iter(counts)) <= 0:
            raise ValueError("public sequence lengths disagree or are empty")
        count = next(iter(counts))
        entity_ids = self.arrays["entity_ids"]
        if entity_ids.ndim != 2:
            raise ValueError("invalid entity ID shape")
        if not np.isin(self.arrays["terminal_status"], [-1, 0, 1]).all():
            raise ValueError("invalid terminal status")
        if not np.isin(self.arrays["board_rotated"], [-1, 0, 1]).all():
            raise ValueError("invalid board rotation")
        expected_shapes = {
            "board_rotated": (count,),
            "terminal_status": (count,),
            "entity_features": (*entity_ids.shape, ENTITY_FEATURE_SIZE),
            "entity_mask": entity_ids.shape,
            "hand_ids": (count, VISIBLE_CARD_SLOTS),
            "global_features": (count, ACTOR_GLOBAL_SIZE),
            "opponent_history_ages": self.arrays["opponent_history_ids"].shape,
        }
        for name, shape in expected_shapes.items():
            if self.arrays[name].shape != shape:
                raise ValueError(f"invalid public shape {name}")
        for name in ("opponent_history_ids", "opponent_seen_card_ids"):
            if self.arrays[name].ndim != 2:
                raise ValueError(f"invalid public shape {name}")
        confidence_sources = dict(
            zip(
                CONFIDENCE_FIELDS,
                ("entity_ids", "entity_features", "hand_ids", "global_features"),
            )
        )
        for name, source in confidence_sources.items():
            if name in self.arrays:
                confidence = self.arrays[name]
                if (
                    confidence.shape != self.arrays[source].shape
                    or (confidence < 0).any()
                    or (confidence > 1).any()
                ):
                    raise ValueError(f"invalid public confidence {name}")
        ids = self.arrays["own_last_play_ids"]
        features = self.arrays["own_last_play_features"]
        if ids.ndim != 1 or features.shape != (len(ids), 2):
            raise ValueError("invalid own-history dimensions")
        known = features[:, 0]
        if (
            not np.isin(known, [0, 1]).all()
            or not np.array_equal(ids >= 2, known == 1)
            or (ids == 1).any()
        ):
            raise ValueError("accepted-play identity and knowledge disagree")
        if (
            (features < 0).any()
            or (features > 1).any()
            or (features[known == 0, 1] != 0).any()
        ):
            raise ValueError("invalid accepted-play cost")
        if not np.allclose(
            features[:, 1] * 10, np.rint(features[:, 1] * 10), atol=1e-6
        ):
            raise ValueError("accepted-play cost must represent whole elixir")
        for identity in ids[ids >= 2]:
            name = self.token_names[identity]
            if ":" in name and not name.startswith("card_action:"):
                raise ValueError("accepted-play identity must be a card action")

    @classmethod
    def from_observations(
        cls, builder: StructuredObservationBuilder, observations: list[ActorObservation]
    ):
        if not observations:
            raise ValueError("empty public sequence")
        rows = {name: [] for name in ARRAY_DTYPES}
        confidence_present = {
            name
            for name in CONFIDENCE_FIELDS
            if getattr(observations[0], name, None) is not None
        }
        rows.update({name: [] for name in confidence_present})
        first = getattr(observations[0], 'observation', observations[0])
        level_present = {name for name in LEVEL_DTYPES if getattr(first, name, None) is not None}
        if level_present and level_present != set(LEVEL_DTYPES):
            raise ValueError('incomplete public entity level fields')
        rows.update({name: [] for name in level_present})
        for observation in observations:
            payload = getattr(observation, "observation", observation)
            if {name for name in LEVEL_DTYPES if getattr(payload, name, None) is not None} != level_present:
                raise ValueError('entity level contract changes within sequence')
            present = {
                name
                for name in CONFIDENCE_FIELDS
                if getattr(observation, name, None) is not None
            }
            if present != confidence_present:
                raise ValueError("confidence contract changes within sequence")
            for name in set(rows) - {"own_last_play_ids", "own_last_play_features", "terminal_status", "board_rotated"}:
                source = observation if name in confidence_present else payload
                value = np.asarray(getattr(source, name))
                expected = ARRAY_DTYPES.get(name, LEVEL_DTYPES.get(name, np.dtype("float32")))
                if value.dtype != expected:
                    raise ValueError(f"public source dtype mismatch for {name}")
                rows[name].append(value)
            if payload.terminal is not None and type(payload.terminal) is not bool:
                raise ValueError("terminal status must be bool or unknown")
            rows["terminal_status"].append(-1 if payload.terminal is None else int(payload.terminal))
            if payload.board_rotated is not None and type(payload.board_rotated) is not bool:
                raise ValueError("board rotation must be bool or unknown")
            rows["board_rotated"].append(-1 if payload.board_rotated is None else int(payload.board_rotated))
            accepted = payload.own_last_play
            identity = (
                0
                if accepted is None
                else builder.token_id(accepted.card_name, namespace="card_action")
            )
            if accepted is not None and identity <= 1:
                raise ValueError("accepted own card is outside the declared vocabulary")
            rows["own_last_play_ids"].append(identity)
            rows["own_last_play_features"].append(
                [
                    float(accepted is not None),
                    0.0 if accepted is None else accepted.elixir_cost / 10,
                ]
            )
        arrays = {
            name: np.asarray(values, dtype=ARRAY_DTYPES.get(name, LEVEL_DTYPES.get(name, np.dtype("float32"))))
            for name, values in rows.items()
        }
        return cls(builder.token_names, arrays)

    def save(self, path: Path):
        self.__post_init__()
        metadata = json.dumps(
            {"schema": "clasher.public-policy.v5", "token_names": self.token_names},
            separators=(",", ":"),
        )
        with path.open("xb") as stream:
            np.savez_compressed(stream, metadata=np.asarray(metadata), **self.arrays)

    @classmethod
    def load(cls, path: Path, *, token_names: tuple[str, ...]):
        with np.load(path, allow_pickle=False) as archive:
            metadata = json.loads(str(archive["metadata"].item()))
            if (
                set(metadata) != {"schema", "token_names"}
                or metadata["schema"] not in {"clasher.public-policy.v3", "clasher.public-policy.v4", "clasher.public-policy.v5"}
            ):
                raise ValueError("unsupported public policy schema")
            if tuple(metadata["token_names"]) != token_names:
                raise ValueError("public token vocabulary mismatch")
            arrays = {
                name: archive[name].copy()
                for name in archive.files
                if name != "metadata"
            }
        if metadata['schema'] != 'clasher.public-policy.v5' and ('entity_levels' in arrays) != (metadata['schema'] == 'clasher.public-policy.v4'):
            raise ValueError('public level fields disagree with archive version')
        if metadata['schema'] != 'clasher.public-policy.v5':
            if 'board_rotated' in arrays:
                raise ValueError('board rotation requires archive version 5')
            arrays['board_rotated'] = np.full(len(arrays['terminal_status']), -1, dtype=np.int8)
        return cls(token_names, arrays)

    def validate_action_mask(self, mask: np.ndarray) -> None:
        # Match lifecycle is control metadata, not an extra learned feature.
        from .common import NUM_HAND_SLOTS, NUM_TILES

        no_op = NUM_HAND_SLOTS * NUM_TILES
        count = len(self.arrays["terminal_status"])
        if mask.dtype != np.bool_:
            raise ValueError("public action mask must be boolean")
        if mask.shape != (count, no_op + 2):
            raise ValueError("invalid public action mask shape")
        inactive = self.arrays["terminal_status"] != 0
        allowed = np.zeros(no_op + 2, dtype=bool)
        allowed[no_op] = True
        if np.any(mask[inactive] != allowed):
            raise ValueError("ended or unknown observations require a wait-only mask")

    def policy_inputs(
        self,
        *,
        action_mask,
        previous_actions,
        previous_rewards,
        episode_starts,
        device="cpu",
    ):
        """Return one batch containing the stored sequence, without critic state."""
        self.__post_init__()
        count = len(self.arrays["own_last_play_ids"])
        mask = np.asarray(action_mask)
        self.validate_action_mask(mask)
        actions = np.asarray(previous_actions)
        rewards = np.asarray(previous_rewards)
        starts = np.asarray(episode_starts)
        if any(array.shape != (count,) for array in (actions, rewards, starts)):
            raise ValueError("public controls require one scalar per observation")
        if actions.dtype.kind not in "iu" or ((actions < 0) | (actions >= mask.shape[1])).any():
            raise ValueError("previous actions must be valid integer action IDs")
        if rewards.dtype.kind not in "iuf" or not np.isfinite(rewards).all():
            raise ValueError("previous rewards must be finite numeric values")
        with np.errstate(over="ignore", invalid="ignore"):
            rewards = rewards.astype(np.float32)
        if not np.isfinite(rewards).all():
            raise ValueError("previous rewards must fit finite float32 values")
        if starts.dtype != np.bool_:
            raise ValueError("episode starts must be boolean")
        controls = {
            "action_mask": mask,
            "previous_actions": actions.astype(np.int64),
            "previous_rewards": rewards,
            "episode_starts": starts,
        }
        policy_arrays = {k: v for k, v in self.arrays.items() if k not in {"terminal_status", "board_rotated"}}
        return PolicyInputs(
            **{
                name: torch.as_tensor(array.copy(), device=device).unsqueeze(0)
                for name, array in (policy_arrays | controls).items()
            }
        )
