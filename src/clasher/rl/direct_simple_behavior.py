"""Complete-episode corpus contract for direct-Simple behavior reproduction."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

TRANSITION_KEYS: Final = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "hand_ids",
    "global_features",
    "entity_id_confidence",
    "entity_feature_confidence",
    "hand_id_confidence",
    "global_feature_confidence",
    "action_masks",
    "previous_actions",
    "previous_rewards",
    "episode_starts",
    "actions",
    "old_log_probs",
    "rewards",
    "dones",
)


@dataclass(frozen=True)
class DirectSimpleBehaviorCorpus:
    """Flattened complete episodes plus exact reset recurrent states."""

    arrays: dict[str, np.ndarray]
    episode_offsets: NDArray[np.int64]
    episode_stream_rows: NDArray[np.int64]
    episode_ordinals: NDArray[np.int64]
    initial_hidden: np.ndarray
    initial_cell: np.ndarray
    episode_arrays: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def episode_count(self) -> int:
        return int(self.episode_stream_rows.size)

    @property
    def row_count(self) -> int:
        return int(self.episode_offsets[-1])


@dataclass(frozen=True)
class RecurrentBehaviorWindow:
    """One supervised segment with a preceding recurrent burn-in prefix."""

    episode: int
    context_start: int
    train_start: int
    end: int

    @property
    def burn_in_rows(self) -> int:
        return self.train_start - self.context_start

    @property
    def train_rows(self) -> int:
        return self.end - self.train_start


def recurrent_behavior_windows(
    episode_offsets: NDArray[np.int64],
    *,
    train_steps: int,
    burn_in_steps: int,
) -> tuple[RecurrentBehaviorWindow, ...]:
    """Cover every episode row once while exposing only preceding context."""

    offsets = np.asarray(episode_offsets, dtype=np.int64)
    if offsets.ndim != 1 or offsets.size < 2 or int(offsets[0]) != 0:
        raise ValueError("episode offsets must begin at zero")
    if bool((np.diff(offsets) <= 0).any()):
        raise ValueError("behavior windows require nonempty episodes")
    if train_steps < 1 or burn_in_steps < 0:
        raise ValueError("train steps must be positive and burn-in non-negative")
    windows: list[RecurrentBehaviorWindow] = []
    for episode in range(offsets.size - 1):
        begin = int(offsets[episode])
        stop = int(offsets[episode + 1])
        for train_start in range(begin, stop, train_steps):
            windows.append(
                RecurrentBehaviorWindow(
                    episode=episode,
                    context_start=max(begin, train_start - burn_in_steps),
                    train_start=train_start,
                    end=min(stop, train_start + train_steps),
                )
            )
    return tuple(windows)


class CompleteEpisodeBuilder:
    """Accumulate asynchronous rollout rows and publish only terminal episodes."""

    def __init__(
        self,
        *,
        stream_count: int,
        episodes_per_stream: int,
        reset_hidden: np.ndarray,
        reset_cell: np.ndarray,
        extra_transition_keys: tuple[str, ...] = (),
    ) -> None:
        if stream_count < 1 or episodes_per_stream < 1:
            raise ValueError("stream and episode counts must be positive")
        expected = (stream_count,)
        if reset_hidden.ndim != 2 or reset_hidden.shape[:1] != expected:
            raise ValueError("reset hidden state must be [streams, memory]")
        if reset_cell.shape != reset_hidden.shape:
            raise ValueError("reset hidden and cell state shapes differ")
        self.stream_count = int(stream_count)
        self.episodes_per_stream = int(episodes_per_stream)
        self.reset_hidden = np.asarray(reset_hidden).copy()
        self.reset_cell = np.asarray(reset_cell).copy()
        if len(set(extra_transition_keys)) != len(extra_transition_keys) or set(
            extra_transition_keys
        ).intersection(TRANSITION_KEYS):
            raise ValueError("extra transition keys must be unique and new")
        self.transition_keys = (*TRANSITION_KEYS, *extra_transition_keys)
        self._active: list[dict[str, list[np.ndarray]] | None] = [
            None for _ in range(stream_count)
        ]
        self._completed_by_stream = np.zeros(stream_count, dtype=np.int64)
        self._episodes: list[tuple[int, int, dict[str, np.ndarray]]] = []

    @property
    def complete(self) -> bool:
        return bool((self._completed_by_stream >= self.episodes_per_stream).all())

    @property
    def completed_by_stream(self) -> NDArray[np.int64]:
        return self._completed_by_stream.astype(np.int64, copy=True)

    def add_rollout(self, arrays: dict[str, np.ndarray]) -> None:
        missing = sorted(set(self.transition_keys).difference(arrays))
        if missing:
            raise ValueError(f"rollout is missing behavior arrays: {missing}")
        shape = arrays["actions"].shape
        if len(shape) != 2 or shape[0] != self.stream_count:
            raise ValueError("rollout actions must be [streams, steps]")
        for key in self.transition_keys:
            value = np.asarray(arrays[key])
            if value.shape[:2] != shape:
                raise ValueError(f"rollout {key} does not share [streams, steps]")

        starts = np.asarray(arrays["episode_starts"], dtype=np.bool_)
        dones = np.asarray(arrays["dones"], dtype=np.bool_)
        for stream in range(self.stream_count):
            for step in range(shape[1]):
                if self._completed_by_stream[stream] >= self.episodes_per_stream:
                    continue
                if bool(starts[stream, step]):
                    if self._active[stream] is not None:
                        raise ValueError(
                            "new episode started before the prior one terminated"
                        )
                    self._active[stream] = {key: [] for key in self.transition_keys}
                active = self._active[stream]
                if active is None:
                    raise ValueError("rollout began without an episode-start boundary")
                for key in self.transition_keys:
                    active[key].append(np.asarray(arrays[key][stream, step]).copy())
                if bool(dones[stream, step]):
                    ordinal = int(self._completed_by_stream[stream])
                    episode = {
                        key: np.stack(values, axis=0) for key, values in active.items()
                    }
                    self._episodes.append((stream, ordinal, episode))
                    self._completed_by_stream[stream] += 1
                    self._active[stream] = None

    def finalize(self) -> DirectSimpleBehaviorCorpus:
        if not self.complete:
            raise ValueError("cannot publish an incomplete behavior corpus")
        ordered = sorted(self._episodes, key=lambda item: (item[0], item[1]))
        expected_count = self.stream_count * self.episodes_per_stream
        if len(ordered) != expected_count:
            raise ValueError("completed episode count differs from the requested grid")
        lengths = np.asarray(
            [episode["actions"].shape[0] for _stream, _ordinal, episode in ordered],
            dtype=np.int64,
        )
        offsets = np.concatenate(
            [np.zeros(1, dtype=np.int64), np.cumsum(lengths, dtype=np.int64)]
        )
        streams = np.asarray([stream for stream, _ordinal, _episode in ordered])
        ordinals = np.asarray([ordinal for _stream, ordinal, _episode in ordered])
        arrays = {
            key: np.concatenate(
                [episode[key] for _stream, _ordinal, episode in ordered], axis=0
            )
            for key in self.transition_keys
        }
        hidden = self.reset_hidden[streams].copy()
        cell = self.reset_cell[streams].copy()
        corpus = DirectSimpleBehaviorCorpus(
            arrays=arrays,
            episode_offsets=offsets,
            episode_stream_rows=streams.astype(np.int64, copy=False),
            episode_ordinals=ordinals.astype(np.int64, copy=False),
            initial_hidden=hidden,
            initial_cell=cell,
        )
        validate_direct_simple_behavior_corpus(corpus)
        return corpus


def validate_direct_simple_behavior_corpus(
    corpus: DirectSimpleBehaviorCorpus,
) -> None:
    """Fail closed on chronology, legality, or recurrent-reset corruption."""

    offsets = np.asarray(corpus.episode_offsets)
    if offsets.ndim != 1 or offsets.size < 2 or int(offsets[0]) != 0:
        raise ValueError("episode offsets must begin at zero")
    if bool((np.diff(offsets) <= 0).any()):
        raise ValueError("every published episode must be nonempty")
    episode_count = offsets.size - 1
    if corpus.episode_stream_rows.shape != (episode_count,):
        raise ValueError("episode stream rows do not match offsets")
    if corpus.episode_ordinals.shape != (episode_count,):
        raise ValueError("episode ordinals do not match offsets")
    if (
        corpus.initial_hidden.ndim != 2
        or corpus.initial_hidden.shape[0] != episode_count
    ):
        raise ValueError("initial hidden states do not match episodes")
    if corpus.initial_cell.shape != corpus.initial_hidden.shape:
        raise ValueError("initial recurrent state shapes differ")
    for key, value in corpus.episode_arrays.items():
        if np.asarray(value).shape[:1] != (episode_count,):
            raise ValueError(f"corpus {key} episode count differs from offsets")
    row_count = int(offsets[-1])
    missing = sorted(set(TRANSITION_KEYS).difference(corpus.arrays))
    if missing:
        raise ValueError(f"corpus is missing behavior arrays: {missing}")
    for key, value in corpus.arrays.items():
        if np.asarray(value).shape[:1] != (row_count,):
            raise ValueError(f"corpus {key} row count differs from offsets")

    starts = np.asarray(corpus.arrays["episode_starts"], dtype=np.bool_)
    dones = np.asarray(corpus.arrays["dones"], dtype=np.bool_)
    actions = np.asarray(corpus.arrays["actions"], dtype=np.int64)
    previous_actions = np.asarray(corpus.arrays["previous_actions"], dtype=np.int64)
    rewards = np.asarray(corpus.arrays["rewards"], dtype=np.float32)
    previous_rewards = np.asarray(corpus.arrays["previous_rewards"], dtype=np.float32)
    action_masks = np.asarray(corpus.arrays["action_masks"], dtype=np.bool_)
    if action_masks.ndim != 2 or action_masks.shape[0] != row_count:
        raise ValueError("action masks must be [rows, actions]")
    if actions.shape != (row_count,) or previous_actions.shape != (row_count,):
        raise ValueError("actions and previous actions must be one-dimensional")
    if rewards.shape != (row_count,) or previous_rewards.shape != (row_count,):
        raise ValueError("rewards and previous rewards must be one-dimensional")
    if bool(((actions < 0) | (actions >= action_masks.shape[1])).any()):
        raise ValueError("teacher action is outside the action space")
    if not bool(action_masks[np.arange(row_count), actions].all()):
        raise ValueError("teacher action is not legal under the public mask")

    for episode in range(episode_count):
        begin = int(offsets[episode])
        end = int(offsets[episode + 1])
        if not bool(starts[begin]) or bool(starts[begin + 1 : end].any()):
            raise ValueError("episode-start markers do not match episode offsets")
        if bool(dones[begin : end - 1].any()) or not bool(dones[end - 1]):
            raise ValueError(
                "every published episode must end at its first terminal row"
            )
        if end - begin > 1:
            if not np.array_equal(
                previous_actions[begin + 1 : end], actions[begin : end - 1]
            ):
                raise ValueError("previous-action chronology is corrupted")
            if not np.allclose(
                previous_rewards[begin + 1 : end],
                rewards[begin : end - 1],
                atol=1e-7,
                rtol=0.0,
            ):
                raise ValueError("previous-reward chronology is corrupted")


def load_direct_simple_behavior_corpus(
    path: str | Path,
) -> tuple[dict[str, Any], DirectSimpleBehaviorCorpus]:
    """Load and fully validate a published direct-Simple behavior archive."""

    with np.load(Path(path), allow_pickle=False) as archive:
        required = {
            *TRANSITION_KEYS,
            "episode_offsets",
            "episode_stream_rows",
            "episode_ordinals",
            "initial_hidden",
            "initial_cell",
            "metadata_json",
        }
        missing = sorted(required.difference(archive.files))
        if missing:
            raise ValueError(f"behavior archive is missing arrays: {missing}")
        metadata = json.loads(str(archive["metadata_json"].item()))
        if not isinstance(metadata, dict):
            raise TypeError("behavior metadata must be a JSON object")
        structural = {
            "episode_offsets",
            "episode_stream_rows",
            "episode_ordinals",
            "initial_hidden",
            "initial_cell",
            "metadata_json",
        }
        episode_names = {
            "episode_opponent_indices",
            "episode_learner_players",
            "episode_final_outcomes",
            "episode_terminal_tower_margins",
            "episode_battle_indices",
            "episode_opponent_deck_indices",
        }.intersection(archive.files)
        corpus = DirectSimpleBehaviorCorpus(
            arrays={
                key: archive[key].copy()
                for key in archive.files
                if key not in structural and key not in episode_names
            },
            episode_offsets=archive["episode_offsets"].astype(np.int64, copy=True),
            episode_stream_rows=archive["episode_stream_rows"].astype(
                np.int64, copy=True
            ),
            episode_ordinals=archive["episode_ordinals"].astype(np.int64, copy=True),
            initial_hidden=archive["initial_hidden"].copy(),
            initial_cell=archive["initial_cell"].copy(),
            episode_arrays={key: archive[key].copy() for key in episode_names},
        )
    validate_direct_simple_behavior_corpus(corpus)
    if metadata.get("complete_episodes_only") is not True:
        raise ValueError("behavior metadata does not guarantee complete episodes")
    if int(metadata.get("episode_count", -1)) != corpus.episode_count:
        raise ValueError("behavior metadata episode count differs from the archive")
    if int(metadata.get("row_count", -1)) != corpus.row_count:
        raise ValueError("behavior metadata row count differs from the archive")
    return metadata, corpus


__all__ = [
    "TRANSITION_KEYS",
    "CompleteEpisodeBuilder",
    "DirectSimpleBehaviorCorpus",
    "RecurrentBehaviorWindow",
    "load_direct_simple_behavior_corpus",
    "recurrent_behavior_windows",
    "validate_direct_simple_behavior_corpus",
]
