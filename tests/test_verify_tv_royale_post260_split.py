from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.verify_tv_royale_post260_split import verify_post260_split


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    run = tmp_path / "run.json"
    split = tmp_path / "split.json"
    completed = [f"game-{index}" for index in range(10)]
    corpora: dict[str, Path] = {}
    for replay in completed:
        corpus = tmp_path / f"{replay}.npz"
        np.savez_compressed(corpus, hand_ids=np.asarray([[1, 2, 3, 4]], dtype=np.int64))
        corpora[replay] = corpus
    _write(
        run,
        {
            "records": [
                *(
                    {
                        "status": "complete",
                        "replay": replay,
                        "corpus": str(corpora[replay]),
                        "corpus_sha256": _sha256(corpora[replay]),
                    }
                    for replay in completed[:4]
                ),
                {"status": "failed", "replay": "ignored"},
                *(
                    {
                        "status": "complete",
                        "replay": replay,
                        "corpus": str(corpora[replay]),
                        "corpus_sha256": _sha256(corpora[replay]),
                    }
                    for replay in completed[4:]
                ),
            ]
        },
    )
    partitions = {
        "train": completed[2:4],
        "validation": completed[4:6],
        "archetype_test": completed[6:8],
        "chronology_test": completed[8:10],
    }
    _write(
        split,
        {
            "source_run_manifest": str(run),
            "source_run_manifest_sha256": _sha256(run),
            "source_replays": 10,
            "reserved_final_evaluation_replays": 2,
            "reserved_replay_ids": completed[:2],
            "total_replays": 8,
            "splits": {
                name: {
                    "replays": len(replays),
                    "source_replays_considered": len(replays),
                    "replays_removed_no_complete_hand": 0,
                    "replay_ids": replays,
                }
                for name, replays in partitions.items()
            },
            "invariants": {
                "replay_overlap": 0,
                "deck_signature_overlap": 0,
                "held_out_archetype_train_overlap": 0,
            },
        },
    )
    return run, split


def test_post260_verifier_proves_exact_chronology_partition(tmp_path: Path) -> None:
    run, split = _fixture(tmp_path)

    result = verify_post260_split(
        split_manifest_path=split,
        run_manifest_path=run,
        target_games=10,
        reserved_games=2,
    )

    assert result["status"] == "post260_inputs_verified"
    assert result["reserved_replays"] == 2
    assert result["partition_replays"] == 8
    assert result["excluded_no_complete_hand_replays"] == 0


def test_post260_verifier_rejects_same_size_wrong_prefix(tmp_path: Path) -> None:
    run, split = _fixture(tmp_path)
    payload = json.loads(split.read_text(encoding="utf-8"))
    payload["reserved_replay_ids"] = ["game-0", "game-2"]
    _write(split, payload)

    with pytest.raises(ValueError, match="exact development prefix"):
        verify_post260_split(
            split_manifest_path=split,
            run_manifest_path=run,
            target_games=10,
            reserved_games=2,
        )


def test_post260_verifier_rejects_missing_or_duplicate_partition_game(
    tmp_path: Path,
) -> None:
    run, split = _fixture(tmp_path)
    payload = json.loads(split.read_text(encoding="utf-8"))
    payload["splits"]["chronology_test"]["replay_ids"] = ["game-8", "game-8"]
    _write(split, payload)

    with pytest.raises(ValueError, match="more than one"):
        verify_post260_split(
            split_manifest_path=split,
            run_manifest_path=run,
            target_games=10,
            reserved_games=2,
        )


def test_post260_verifier_accepts_exact_complete_hand_exclusions(tmp_path: Path) -> None:
    run, split = _fixture(tmp_path)
    run_payload = json.loads(run.read_text(encoding="utf-8"))
    excluded = run_payload["records"][-1]
    corpus = Path(excluded["corpus"])
    np.savez_compressed(corpus, hand_ids=np.asarray([[1, 2, 0, 4]], dtype=np.int64))
    excluded["corpus_sha256"] = _sha256(corpus)
    _write(run, run_payload)

    payload = json.loads(split.read_text(encoding="utf-8"))
    payload["source_run_manifest_sha256"] = _sha256(run)
    chronology = payload["splits"]["chronology_test"]
    chronology["replay_ids"].remove(excluded["replay"])
    chronology["replays"] -= 1
    chronology["replays_removed_no_complete_hand"] = 1
    payload["total_replays"] -= 1
    _write(split, payload)

    result = verify_post260_split(
        split_manifest_path=split,
        run_manifest_path=run,
        target_games=10,
        reserved_games=2,
    )

    assert result["partition_replays"] == 7
    assert result["excluded_no_complete_hand_replays"] == 1
