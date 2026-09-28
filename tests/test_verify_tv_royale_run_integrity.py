from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.oracle_corpus import file_sha256
from scripts.verify_tv_royale_run_integrity import (
    _verify_exact_unique_members,
    _verify_public_state_sidecar,
    verify_run_integrity,
)


def _manifest(records: list[dict[str, object]], *, target: int) -> dict[str, object]:
    complete = sum(row["status"] == "complete" for row in records)
    failed = sum(row["status"] == "failed" for row in records)
    return {
        "schema": "tv-royale-raw-cascade-run-v1",
        "target_games": target,
        "completed_games": complete,
        "failed_games": failed,
        "attempted_games": len(records),
        "records": records,
    }


def test_rejects_duplicate_completed_replay_before_artifact_reads(
    tmp_path: Path,
) -> None:
    path = tmp_path / "run_manifest.json"
    path.write_text(
        json.dumps(
            _manifest(
                [
                    {"status": "complete", "replay": "same"},
                    {"status": "complete", "replay": "same"},
                ],
                target=2,
            )
        )
    )

    with pytest.raises(ValueError, match="duplicate replay"):
        verify_run_integrity(path, scratch_root=tmp_path, target_games=2)


def test_rejects_counter_record_disagreement(tmp_path: Path) -> None:
    path = tmp_path / "run_manifest.json"
    payload = _manifest(
        [{"status": "complete", "replay": "one"}],
        target=1,
    )
    payload["completed_games"] = 0
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="counter disagrees"):
        verify_run_integrity(path, scratch_root=tmp_path, target_games=1)


def test_exact_member_verifier_accepts_order_independent_membership() -> None:
    _verify_exact_unique_members(
        ["replay-b", "replay-a"],
        ["replay-a", "replay-b"],
        label="test members",
    )


def test_exact_member_verifier_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="duplicate members"):
        _verify_exact_unique_members(
            ["replay-a", "replay-a"],
            ["replay-a"],
            label="test members",
        )


def test_exact_member_verifier_rejects_substitution() -> None:
    with pytest.raises(ValueError, match="membership mismatch"):
        _verify_exact_unique_members(
            ["replay-a", "replay-c"],
            ["replay-a", "replay-b"],
            label="test members",
        )


def _write_public_fixture(tmp_path: Path) -> tuple[Path, Path]:
    corpus = tmp_path / "corpus.npz"
    np.savez_compressed(
        corpus,
        source_indices=np.asarray([4], dtype=np.int64),
        source_frames=np.asarray([40], dtype=np.int64),
        source_replays=np.asarray(["replay-a"]),
        expert_actions=np.asarray([7], dtype=np.int64),
    )
    sidecar = tmp_path / "public_state_v2.npz"
    np.savez_compressed(
        sidecar,
        entity_ids=np.asarray([[2, 0]], dtype=np.int64),
        entity_features=np.asarray(
            [[[0.5] * 32, [0.0] * 32]], dtype=np.float16
        ),
        entity_mask=np.asarray([[True, False]]),
        entity_id_confidence=np.asarray([[0.8, 0.0]], dtype=np.float32),
        entity_feature_confidence=np.asarray(
            [[[0.8] * 32, [0.0] * 32]], dtype=np.float32
        ),
        hand_ids=np.asarray([[1, 2, 3, 4, 0]], dtype=np.int64),
        hand_id_confidence=np.asarray([[1, 1, 1, 1, 0]], dtype=np.float32),
        global_features=np.asarray([[0.5] * 18], dtype=np.float32),
        global_feature_confidence=np.asarray([[1.0] * 18], dtype=np.float32),
        opponent_history_ids=np.zeros((1, 0), dtype=np.int64),
        opponent_history_ages=np.zeros((1, 0), dtype=np.float32),
        opponent_history_confidence=np.zeros((1, 0), dtype=np.float32),
        opponent_seen_card_ids=np.zeros((1, 0), dtype=np.int64),
        opponent_seen_card_confidence=np.zeros((1, 0), dtype=np.float32),
        source_indices=np.asarray([4], dtype=np.int64),
        source_frames=np.asarray([40], dtype=np.int64),
        expert_actions=np.asarray([7], dtype=np.int64),
        schema_version=np.asarray(2),
    )
    return corpus, sidecar


def test_public_state_sidecar_reverifies_confidence_and_alignment(
    tmp_path: Path,
) -> None:
    corpus, sidecar = _write_public_fixture(tmp_path)

    result = _verify_public_state_sidecar(
        sidecar,
        expected_sha256=file_sha256(sidecar),
        expected_samples=1,
        corpus_path=corpus,
    )

    assert result == {
        "samples": 1,
        "visible_entities": 1,
        "entities_with_hp": 1,
        "entities_with_motion": 1,
        "entity_hp_coverage": 1.0,
        "motion_coverage": 1.0,
    }


def test_public_state_sidecar_rejects_fabricated_missing_values(
    tmp_path: Path,
) -> None:
    corpus, sidecar = _write_public_fixture(tmp_path)
    with np.load(sidecar, allow_pickle=False) as source:
        payload = {name: source[name].copy() for name in source.files}
    payload["entity_features"][0, 0, 9] = 0.75
    payload["entity_feature_confidence"][0, 0, 9] = 0.0
    np.savez_compressed(sidecar, **payload)

    with pytest.raises(ValueError, match="fabricates entity_features"):
        _verify_public_state_sidecar(
            sidecar,
            expected_sha256=file_sha256(sidecar),
            expected_samples=1,
            corpus_path=corpus,
        )
