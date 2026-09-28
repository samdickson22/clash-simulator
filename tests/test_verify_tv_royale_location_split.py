from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.imitation import CorpusMetadata
from clasher.rl.oracle_corpus import file_sha256
from scripts.verify_tv_royale_location_split import (
    EXPECTED_SCHEMA,
    REQUIRED_INVARIANTS,
    SPLIT_MINIMUMS,
    LocationDataInsufficient,
    verify_location_split,
)

TARGET_GAMES = 2_000


def _write_corpus(path: Path, *, samples: int) -> None:
    metadata = CorpusMetadata(
        schema_version=1,
        created_at="2026-08-13T00:00:00Z",
        seed=1045801,
        decisions=samples,
        samples=samples,
        decision_interval=8,
        max_ticks=6_000,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=1,
        token_names=("unknown",),
        label_source="mixed-rehearsal",
    )
    action_masks = np.ones((samples, 4), dtype=np.bool_)
    np.savez_compressed(
        path,
        entity_ids=np.zeros((samples, 1), dtype=np.int64),
        entity_features=np.zeros((samples, 1, 1), dtype=np.float32),
        entity_mask=np.ones((samples, 1), dtype=np.bool_),
        hand_ids=np.zeros((samples, 4), dtype=np.int64),
        global_features=np.zeros((samples, 1), dtype=np.float32),
        action_masks=action_masks,
        previous_actions=np.full(samples, 2, dtype=np.int64),
        previous_rewards=np.zeros(samples, dtype=np.float32),
        episode_starts=np.ones(samples, dtype=np.bool_),
        expert_actions=np.zeros(samples, dtype=np.int64),
        episode_ids=np.arange(samples, dtype=np.int64),
        metadata_json=np.asarray(metadata.to_json()),
    )


def _manifest(tmp_path: Path) -> dict[str, object]:
    splits = {}
    source_splits = {}
    total_samples = 0
    for name, minimums in SPLIT_MINIMUMS.items():
        samples = int(minimums["samples"])
        replays = int(minimums["replays"])
        total_samples += samples
        replay_ids = [f"{name}-replay-{index}" for index in range(replays)]
        corpus_path = tmp_path / f"{name}.npz"
        _write_corpus(corpus_path, samples=samples)
        corpus_manifest_path = tmp_path / f"{name}_manifest.json"
        base, remainder = divmod(samples, replays)
        sources = [
            {
                "selected_samples": base + int(index < remainder),
                "label_source": REQUIRED_INVARIANTS["location_label_source"],
            }
            for index in range(replays)
        ]
        corpus_manifest = {
            "schema_version": 1,
            "output": str(corpus_path.resolve()),
            "output_sha256": file_sha256(corpus_path),
            "samples": samples,
            "independent_rows": True,
            "sources": sources,
        }
        corpus_manifest_path.write_text(json.dumps(corpus_manifest))
        splits[name] = {
            "samples": samples,
            "replays": replays,
            "replay_ids": replay_ids,
            "output": str(corpus_path.resolve()),
            "output_sha256": file_sha256(corpus_path),
            "manifest": str(corpus_manifest_path.resolve()),
            "manifest_sha256": file_sha256(corpus_manifest_path),
            "diversity": {
                key: value
                for key, value in minimums.items()
                if key not in {"samples", "replays"}
            },
        }
        source_splits[name] = {"replay_ids": replay_ids}

    run_manifest_path = tmp_path / "run_manifest.json"
    run_manifest_path.write_text(json.dumps({"completed_games": TARGET_GAMES}))
    type_manifest_path = tmp_path / "type_split_manifest.json"
    type_manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "source_replays": TARGET_GAMES,
                "reserved_replay_ids": ["reserved-replay"],
                "splits": source_splits,
            }
        )
    )
    assigned_replays = sum(int(row["replays"]) for row in splits.values())
    return {
        "schema": EXPECTED_SCHEMA,
        "target_games": TARGET_GAMES,
        "source_run_manifest": str(run_manifest_path.resolve()),
        "source_run_manifest_sha256": file_sha256(run_manifest_path),
        "source_split_manifest": str(type_manifest_path.resolve()),
        "source_split_manifest_sha256": file_sha256(type_manifest_path),
        "location_samples": total_samples,
        "location_replays": assigned_replays + 1,
        "assigned_location_replays": assigned_replays,
        "ignored_replay_ids": ["reserved-replay"],
        "invariants": dict(REQUIRED_INVARIANTS),
        "splits": splits,
    }


def test_accepts_exact_split_and_diversity_minimums(tmp_path: Path) -> None:
    path = tmp_path / "split_manifest.json"
    path.write_text(json.dumps(_manifest(tmp_path)))

    report = verify_location_split(path, target_games=TARGET_GAMES)

    assert report["status"] == "location_split_verified"
    assert report["split_samples"]["train"] == 200
    assert report["split_diversity"]["chronology_test"][
        "minority_side_fraction"
    ] == pytest.approx(0.10)


def test_reports_semantic_and_lane_coverage_failures(tmp_path: Path) -> None:
    payload = _manifest(tmp_path)
    train = payload["splits"]["train"]  # type: ignore[index]
    train["diversity"]["distinct_target_cards"] = 19  # type: ignore[index]
    train["diversity"]["minority_side_fraction"] = 0.19  # type: ignore[index]
    path = tmp_path / "split_manifest.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(LocationDataInsufficient) as caught:
        verify_location_split(path, target_games=TARGET_GAMES)

    assert set(caught.value.details["train"]) == {
        "distinct_target_cards",
        "minority_side_fraction",
    }


def test_rejects_invariant_mismatch_before_training(tmp_path: Path) -> None:
    payload = _manifest(tmp_path)
    payload["invariants"]["replay_overlap"] = 1  # type: ignore[index]
    path = tmp_path / "split_manifest.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="replay_overlap"):
        verify_location_split(path, target_games=TARGET_GAMES)


def test_rejects_tampered_split_artifact(tmp_path: Path) -> None:
    payload = _manifest(tmp_path)
    path = tmp_path / "split_manifest.json"
    path.write_text(json.dumps(payload))
    output = Path(payload["splits"]["validation"]["output"])  # type: ignore[index]
    output.write_bytes(output.read_bytes() + b"tampered")

    with pytest.raises(ValueError, match="artifact digest mismatch"):
        verify_location_split(path, target_games=TARGET_GAMES)


def test_rejects_replay_outside_type_split_assignment(tmp_path: Path) -> None:
    payload = _manifest(tmp_path)
    payload["splits"]["validation"]["replay_ids"][0] = "outside-replay"  # type: ignore[index]
    path = tmp_path / "split_manifest.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="type-split assignment"):
        verify_location_split(path, target_games=TARGET_GAMES)
