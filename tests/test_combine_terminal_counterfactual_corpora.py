from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from scripts.combine_terminal_counterfactual_corpora import (
    ARRAY_NAMES,
    STRUCTURED_ARRAY_NAMES,
    STRUCTURED_V2_ARRAY_NAMES,
    main,
)


def _write_shard(
    root: Path,
    game: int,
    opponent_path: str,
    *,
    structured: bool = False,
    recurrent: bool = False,
) -> None:
    if recurrent:
        structured = True
    arrays = {
        "features": np.zeros((1, 2), dtype=np.float32),
        "action_masks": np.ones((1, 2306), dtype=np.bool_),
        "base_actions": np.asarray([2304], dtype=np.int64),
        "best_actions": np.asarray([2304], dtype=np.int64),
        "candidate_actions": np.asarray([[2304, -1]], dtype=np.int64),
        "candidate_scores": np.asarray([[0.5, np.nan]], dtype=np.float32),
        "candidate_valid": np.asarray([[True, False]], dtype=np.bool_),
        "candidate_kinds": np.asarray([[1, -1]], dtype=np.int8),
        "candidate_card_ids": np.zeros((1, 2), dtype=np.int64),
        "candidate_card_features": np.zeros((1, 2, 1), dtype=np.float32),
        "candidate_tile_features": np.zeros((1, 2, 1), dtype=np.float32),
        "candidate_policy_logits": np.zeros((1, 2), dtype=np.float32),
        "candidate_policy_log_probabilities": np.zeros((1, 2), dtype=np.float32),
        "candidate_policy_type_log_probabilities": np.zeros(
            (1, 2), dtype=np.float32
        ),
        "candidate_crown_differences": np.zeros((1, 2), dtype=np.int8),
        "candidate_tower_damage_differences": np.zeros(
            (1, 2), dtype=np.float32
        ),
        "candidate_terminal_ticks": np.asarray([[6000, -1]], dtype=np.int32),
        "hand_ids": np.ones((1, 4), dtype=np.int64),
        "game_ids": np.asarray([game], dtype=np.int64),
        "ticks": np.asarray([256], dtype=np.int64),
    }
    if structured:
        arrays.update(
            {
                "structured_entity_ids": np.ones((1, 2), dtype=np.int64),
                "structured_entity_features": np.zeros(
                    (1, 2, 3), dtype=np.float32
                ),
                "structured_entity_mask": np.ones((1, 2), dtype=np.bool_),
                "structured_hand_ids": np.ones((1, 5), dtype=np.int64),
                "structured_global_features": np.zeros((1, 4), dtype=np.float32),
                "structured_opponent_history_ids": np.empty(
                    (1, 0), dtype=np.int64
                ),
                "structured_opponent_history_ages": np.empty(
                    (1, 0), dtype=np.float32
                ),
                "structured_opponent_seen_card_ids": np.empty(
                    (1, 0), dtype=np.int64
                ),
                "structured_previous_actions": np.asarray([2304], dtype=np.int64),
                "structured_previous_rewards": np.asarray([0.0], dtype=np.float32),
                "structured_episode_starts": np.asarray([False], dtype=np.bool_),
            }
        )
        if recurrent:
            arrays.update(
                {
                    "structured_recurrent_cell": np.zeros(
                        (1, 64), dtype=np.float32
                    ),
                    "structured_previous_play_hazard": np.zeros(
                        (1, 1), dtype=np.float32
                    ),
                }
            )
            assert set(arrays) == {
                *ARRAY_NAMES,
                *STRUCTURED_ARRAY_NAMES,
                *STRUCTURED_V2_ARRAY_NAMES,
            }
        else:
            assert set(arrays) == {*ARRAY_NAMES, *STRUCTURED_ARRAY_NAMES}
    else:
        assert set(arrays) == set(ARRAY_NAMES)
    path = root / f"game_{game:06d}.npz"
    np.savez_compressed(path, **arrays)
    report = {
        "schema_version": 2,
        "policy": "policy.pt",
        "outcome": None,
        "sampling_decks_path": None,
        "learner_sampling_decks_path": "hog.json",
        "opponent_sampling_decks_path": opponent_path,
        "candidate_card_semantics_version": 3,
        "candidate_card_feature_size": 1,
        "best_action_order": "outcome-crowns-tower-damage-v1",
        "input_sha256": {
            "policy": "a" * 64,
            "decks": "b" * 64,
            "outcome": None,
            "sampling_decks": None,
            "learner_sampling_decks": "c" * 64,
            "opponent_sampling_decks": "d" * 64,
        },
        "collection_config": {
            "decision_interval": 8,
            "max_ticks": 6000,
            "states_per_game": 1,
        },
        "structured_state_contract": (
            "public-actor-v2-action-time-recurrence"
            if recurrent
            else "public-actor-v1"
            if structured
            else None
        ),
        "query_schedule": "phase-balanced" if recurrent else "first-eligible",
        "query_target_ticks": [256, 3120] if recurrent else [],
        "states": [
            {
                "game": game,
                "tick": 256,
                "decisive_improvement": False,
                "base_score": 0.5,
            }
        ],
        "games": [{"game": game}],
    }
    path.with_suffix(".json").write_text(json.dumps(report), encoding="utf-8")


def test_combine_counterfactual_corpora_rejects_mixed_opponent_pools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_shard(tmp_path, 0, "train-a.json")
    _write_shard(tmp_path, 1, "train-b.json")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "combine",
            "--input-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "combined.npz"),
            "--report",
            str(tmp_path / "combined.json"),
        ],
    )

    with pytest.raises(ValueError, match="authorities do not match"):
        main()


def test_combine_counterfactual_corpora_preserves_structured_public_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_shard(tmp_path, 0, "train.json", structured=True)
    _write_shard(tmp_path, 1, "train.json", structured=True)
    output = tmp_path / "combined.npz"
    report = tmp_path / "combined.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "combine",
            "--input-root",
            str(tmp_path),
            "--pattern",
            "game_*.npz",
            "--output",
            str(output),
            "--report",
            str(report),
        ],
    )

    main()

    with np.load(output, allow_pickle=False) as payload:
        assert set(payload.files) == {*ARRAY_NAMES, *STRUCTURED_ARRAY_NAMES}
        assert payload["structured_entity_features"].shape == (2, 2, 3)
    assert json.loads(report.read_text())["structured_state_contract"] == (
        "public-actor-v1"
    )


def test_combine_counterfactual_corpora_rejects_mixed_structured_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_shard(tmp_path, 0, "train.json", structured=True)
    _write_shard(tmp_path, 1, "train.json", structured=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "combine",
            "--input-root",
            str(tmp_path),
            "--pattern",
            "game_*.npz",
            "--output",
            str(tmp_path / "combined.npz"),
            "--report",
            str(tmp_path / "combined.json"),
        ],
    )

    with pytest.raises(ValueError, match="authorities do not match"):
        main()


def test_combine_counterfactual_corpora_preserves_recurrent_v2_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_shard(tmp_path, 0, "train.json", recurrent=True)
    _write_shard(tmp_path, 1, "train.json", recurrent=True)
    output = tmp_path / "combined.npz"
    report = tmp_path / "combined.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "combine",
            "--input-root",
            str(tmp_path),
            "--pattern",
            "game_*.npz",
            "--output",
            str(output),
            "--report",
            str(report),
        ],
    )

    main()

    with np.load(output, allow_pickle=False) as payload:
        assert set(payload.files) == {
            *ARRAY_NAMES,
            *STRUCTURED_ARRAY_NAMES,
            *STRUCTURED_V2_ARRAY_NAMES,
        }
        assert payload["structured_recurrent_cell"].shape == (2, 64)
        assert payload["structured_previous_play_hazard"].shape == (2, 1)
    result = json.loads(report.read_text())
    assert result["structured_state_contract"] == (
        "public-actor-v2-action-time-recurrence"
    )
    assert result["query_schedule"] == "phase-balanced"
    assert result["query_target_ticks"] == [256, 3120]
