"""Undiscounted complete-game labels for actor-visible outcome learning."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

from .direct_simple_behavior import DirectSimpleBehaviorCorpus

OWN_TOWER_START = 8
ENEMY_TOWER_START = 11
TOWER_COUNT = 3


@dataclass(frozen=True)
class CompleteOutcomeLabels:
    """Episode and repeated per-decision terminal labels."""

    final_outcomes: NDArray[np.int8]
    terminal_tower_margins: NDArray[np.float32]
    episode_final_outcomes: NDArray[np.int8]
    episode_terminal_tower_margins: NDArray[np.float32]


def complete_outcome_labels(
    *,
    episode_offsets: NDArray[np.int64],
    dones: np.ndarray,
    terminal_winners: np.ndarray,
    next_global_features: np.ndarray,
    episode_learner_players: np.ndarray,
) -> CompleteOutcomeLabels:
    """Derive only future labels; no privileged value enters policy inputs."""

    offsets = np.asarray(episode_offsets, dtype=np.int64)
    episode_count = len(offsets) - 1
    row_count = int(offsets[-1])
    dones = np.asarray(dones, dtype=np.bool_)
    winners = np.asarray(terminal_winners, dtype=np.int64)
    next_globals = np.asarray(next_global_features, dtype=np.float32)
    learners = np.asarray(episode_learner_players, dtype=np.int64)
    if dones.shape != (row_count,) or winners.shape != (row_count,):
        raise ValueError("terminal outcome tensors do not align with corpus rows")
    if next_globals.shape != (row_count, 18):
        raise ValueError("post-action public globals must be [rows, 18]")
    if learners.shape != (episode_count,) or not bool(np.isin(learners, (0, 1)).all()):
        raise ValueError("episode learner seats must be binary and align with offsets")
    if not np.isfinite(next_globals).all():
        raise ValueError("post-action public globals must be finite")
    tower_fractions = next_globals[:, OWN_TOWER_START : ENEMY_TOWER_START + TOWER_COUNT]
    if bool(((tower_fractions < 0.0) | (tower_fractions > 1.0)).any()):
        raise ValueError("public tower fractions must be in [0, 1]")

    episode_outcomes = np.empty(episode_count, dtype=np.int8)
    episode_margins = np.empty(episode_count, dtype=np.float32)
    row_outcomes = np.empty(row_count, dtype=np.int8)
    row_margins = np.empty(row_count, dtype=np.float32)
    for episode in range(episode_count):
        begin = int(offsets[episode])
        end = int(offsets[episode + 1])
        if bool(dones[begin : end - 1].any()) or not bool(dones[end - 1]):
            raise ValueError("outcome labels require complete first-terminal episodes")
        winner = int(winners[end - 1])
        if winner not in (-1, 0, 1):
            raise ValueError("terminal winner must be draw, player zero, or player one")
        learner = int(learners[episode])
        outcome = 0 if winner < 0 else 1 if winner == learner else -1
        terminal = next_globals[end - 1]
        margin = float(
            (
                terminal[OWN_TOWER_START:ENEMY_TOWER_START].sum()
                - terminal[ENEMY_TOWER_START : ENEMY_TOWER_START + TOWER_COUNT].sum()
            )
            / TOWER_COUNT
        )
        episode_outcomes[episode] = outcome
        episode_margins[episode] = margin
        row_outcomes[begin:end] = outcome
        row_margins[begin:end] = margin
    return CompleteOutcomeLabels(
        final_outcomes=row_outcomes,
        terminal_tower_margins=row_margins,
        episode_final_outcomes=episode_outcomes,
        episode_terminal_tower_margins=episode_margins,
    )


def attach_complete_outcomes(
    corpus: DirectSimpleBehaviorCorpus,
) -> DirectSimpleBehaviorCorpus:
    """Attach immutable future labels to a complete behavior corpus."""

    try:
        learners = corpus.episode_arrays["episode_learner_players"]
        terminal_winners = corpus.arrays["terminal_winners"]
        next_globals = corpus.arrays["next_global_features"]
    except KeyError as error:
        raise ValueError("behavior corpus lacks complete-outcome authority") from error
    labels = complete_outcome_labels(
        episode_offsets=corpus.episode_offsets,
        dones=corpus.arrays["dones"],
        terminal_winners=terminal_winners,
        next_global_features=next_globals,
        episode_learner_players=learners,
    )
    arrays = {
        **corpus.arrays,
        "final_outcomes": labels.final_outcomes,
        "terminal_tower_margins": labels.terminal_tower_margins,
    }
    episode_arrays = {
        **corpus.episode_arrays,
        "episode_final_outcomes": labels.episode_final_outcomes,
        "episode_terminal_tower_margins": labels.episode_terminal_tower_margins,
    }
    return replace(corpus, arrays=arrays, episode_arrays=episode_arrays)


__all__ = [
    "CompleteOutcomeLabels",
    "attach_complete_outcomes",
    "complete_outcome_labels",
]
