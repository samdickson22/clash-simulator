from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.imitation import (
    CORPUS_SCHEMA_VERSION,
    PUBLIC_OBSERVATION_SCHEMA_VERSION,
    CorpusMetadata,
    load_corpus,
    load_public_observation_sidecar,
)
from clasher.rl.public_action_mask import PUBLIC_ACTION_MASK_CONTRACT_VERSION
from clasher.rl.public_observation import REAL_PLAY_FEATURE_CONTRACT_VERSION
from clasher.rl.youtube_causal_corpus import public_frame_from_records


def _head(value: str | None, *, score: float = 0.9) -> dict[str, object]:
    return {
        "valid": value is not None,
        "value": value,
        "score": score if value is not None else 0.0,
    }


def test_public_frame_preserves_slots_and_uses_only_current_public_state() -> None:
    neutral = {
        "snapshot_id": "snapshot-7",
        "split_group_id": "replay-3",
        "timestamp_ms": 1200,
        "public": {
            "entities": [
                {
                    "identity": {
                        "valid": True,
                        "stable_key": "troop_body:HogRider",
                    },
                    "world_position": [4.0, 8.0],
                    "team_id": 1,
                    "confidence": 0.8,
                    "hp_valid": True,
                    "hp_fraction": 0.6,
                    "hp_confidence": 0.7,
                },
                {
                    "identity": {"valid": False, "stable_key": None},
                    "world_position": [9.0, 9.0],
                    "team_id": 0,
                    "confidence": 0.99,
                    "hp_valid": False,
                },
            ],
            "clock": {"valid": True, "value": 177, "confidence": 0.95},
        },
    }
    overlay = {
        "snapshot_id": "snapshot-7",
        "actor_id": 0,
        "own_hud": {
            "hand": [
                _head("card_action:HogRider"),
                _head(None),
                _head("empty"),
                _head("card_action:Fireball", score=0.75),
            ],
            "next_card": _head("card_action:Cannon", score=0.8),
            "elixir": {"valid": True, "value": 6.0, "score": 0.85},
        },
    }

    frame = public_frame_from_records(neutral, overlay, actor_id=0)

    assert frame.own_hand == (
        "card_action:HogRider",
        "<unknown>",
        "<unknown>",
        "card_action:Fireball",
    )
    assert frame.own_hand_confidence == (0.9, 0.0, 0.0, 0.75)
    assert frame.own_next_card == "card_action:Cannon"
    assert frame.own_elixir == 6.0
    assert frame.visible_clock_seconds is None
    assert frame.clock_confidence == 0.0
    assert frame.play_events == ()
    assert len(frame.entities) == 1
    assert frame.entities[0].card == "HogRider"
    assert frame.entities[0].kind == "troop"
    assert frame.entities[0].hp_fraction == pytest.approx(0.6)
    assert frame.entities[0].hp_confidence == pytest.approx(0.7)


def _tiny_corpus(
    path: Path, *, supervision_valid: bool, expert_action: int = 0
) -> None:
    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        seed=1,
        decisions=1,
        samples=1,
        decision_interval=4,
        max_ticks=10,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=1,
        token_names=("<pad>", "<unknown>"),
    )
    action_masks = np.zeros((1, 2306), dtype=np.bool_)
    action_masks[0, 2304] = True
    np.savez_compressed(
        path,
        metadata_json=np.asarray(metadata.to_json()),
        entity_ids=np.zeros((1, 1), dtype=np.int64),
        entity_features=np.zeros((1, 1, 32), dtype=np.float32),
        entity_mask=np.zeros((1, 1), dtype=np.bool_),
        hand_ids=np.zeros((1, 5), dtype=np.int64),
        global_features=np.zeros((1, 18), dtype=np.float32),
        action_masks=action_masks,
        previous_actions=np.asarray([2304], dtype=np.int64),
        previous_rewards=np.zeros((1,), dtype=np.float32),
        episode_starts=np.asarray([True], dtype=np.bool_),
        expert_actions=np.asarray([expert_action], dtype=np.int64),
        episode_ids=np.asarray([0], dtype=np.int64),
        expert_action_supervision_valid=np.asarray(
            [supervision_valid], dtype=np.bool_
        ),
    )


def test_load_corpus_keeps_unsupervised_illegal_action_as_context(
    tmp_path: Path,
) -> None:
    path = tmp_path / "context.npz"
    _tiny_corpus(path, supervision_valid=False)

    _, arrays = load_corpus(path)

    assert arrays["expert_actions"].tolist() == [0]
    assert arrays["expert_action_supervision_valid"].tolist() == [False]


def test_load_corpus_rejects_supervised_illegal_action(tmp_path: Path) -> None:
    path = tmp_path / "invalid.npz"
    _tiny_corpus(path, supervision_valid=True)

    with pytest.raises(ValueError, match="supervised illegal expert action"):
        load_corpus(path)


def test_public_sidecar_preserves_explicit_unsupervised_context(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "context.npz"
    sidecar = tmp_path / "public.npz"
    _tiny_corpus(corpus, supervision_valid=False, expert_action=2304)
    _, arrays = load_corpus(corpus)
    np.savez_compressed(
        sidecar,
        schema_version=np.asarray(PUBLIC_OBSERVATION_SCHEMA_VERSION),
        feature_contract_version=np.asarray(REAL_PLAY_FEATURE_CONTRACT_VERSION),
        action_mask_contract_version=np.asarray(
            PUBLIC_ACTION_MASK_CONTRACT_VERSION
        ),
        entity_ids=arrays["entity_ids"],
        entity_features=arrays["entity_features"],
        entity_mask=arrays["entity_mask"],
        entity_id_confidence=np.zeros_like(
            arrays["entity_ids"], dtype=np.float32
        ),
        entity_feature_confidence=np.zeros_like(
            arrays["entity_features"], dtype=np.float32
        ),
        hand_ids=arrays["hand_ids"],
        hand_id_confidence=np.zeros_like(arrays["hand_ids"], dtype=np.float32),
        global_features=arrays["global_features"],
        global_feature_confidence=np.zeros_like(
            arrays["global_features"], dtype=np.float32
        ),
        action_masks=arrays["action_masks"],
        expert_action_masked=np.asarray([False], dtype=np.bool_),
        expert_actions=arrays["expert_actions"],
        episode_ids=arrays["episode_ids"],
    )

    merged = load_public_observation_sidecar(sidecar, base_arrays=arrays)

    assert merged["expert_action_supervision_valid"].tolist() == [False]
