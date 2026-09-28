from pathlib import Path

import numpy as np
import pytest

from scripts.collect_policy_context_corpus import (
    _component_supervision,
    _contains_unknown_hand_token,
    collect,
)


def test_policy_behavior_spatial_labels_require_behavior_and_teacher_play() -> None:
    no_op = 2304

    assert _component_supervision(
        expert_action=10,
        behavior_action=no_op,
        no_op_action=no_op,
        execute_policy_behavior=True,
    ) == (True, False, False)
    assert _component_supervision(
        expert_action=10,
        behavior_action=no_op,
        no_op_action=no_op,
        execute_policy_behavior=True,
        trust_off_policy_teacher_spatial=True,
    ) == (True, True, True)
    assert _component_supervision(
        expert_action=10,
        behavior_action=20,
        no_op_action=no_op,
        execute_policy_behavior=True,
    ) == (True, True, True)
    assert _component_supervision(
        expert_action=no_op,
        behavior_action=20,
        no_op_action=no_op,
        execute_policy_behavior=True,
    ) == (True, False, False)


def test_teacher_behavior_keeps_ordinary_teacher_spatial_labels() -> None:
    assert _component_supervision(
        expert_action=10,
        behavior_action=10,
        no_op_action=2304,
        execute_policy_behavior=False,
    ) == (True, True, True)


def test_empty_hand_slot_is_not_an_unknown_card_identity() -> None:
    assert not _contains_unknown_hand_token(
        np.asarray([137, 0, 173, 187, 170], dtype=np.int64)
    )
    assert _contains_unknown_hand_token(
        np.asarray([137, 1, 173, 187, 170], dtype=np.int64)
    )


def test_policy_behavior_requires_exactly_one_teacher() -> None:
    common = {
        "checkpoint": Path("missing-behavior.pt"),
        "decks_path": Path("decks.json"),
        "learner_decks_path": Path("learner.json"),
        "opponent_decks_path": Path("opponent.json"),
        "games": 1,
        "seed": 7,
        "corpus_path": Path("corpus.npz"),
        "sidecar_path": Path("sidecar.npz"),
        "manifest_path": Path("manifest.json"),
        "execute_policy_behavior": True,
    }
    with pytest.raises(ValueError, match="requires a teacher"):
        collect(**common)
    with pytest.raises(ValueError, match="only one"):
        collect(
            **common,
            teacher_strategy="balanced",
            teacher_checkpoint=Path("teacher.pt"),
        )
    with pytest.raises(ValueError, match="off-policy spatial trust"):
        collect(
            **common,
            teacher_strategy="balanced",
            trust_off_policy_teacher_spatial=True,
        )
