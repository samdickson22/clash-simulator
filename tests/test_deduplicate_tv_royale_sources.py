from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.deduplicate_tv_royale_sources import (
    build_dedup_report,
    fingerprint_frame,
    inventory_hf_evidence,
    phash_distance,
)


def _image(path: Path, seed: int) -> None:
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 256, size=(96, 54, 3), dtype=np.uint8)
    Image.fromarray(pixels, mode="RGB").save(path)


def _hf_fixture(tmp_path: Path) -> tuple[Path, Path, dict[float, Path]]:
    game = tmp_path / "hf" / "games" / "arena_12" / "replay-a"
    audit = game / "audit"
    audit.mkdir(parents=True)
    frames: dict[float, Path] = {}
    outputs = []
    for fraction, frame, seed in ((0.1, 10, 1), (0.5, 50, 2), (0.9, 90, 3)):
        path = audit / f"frame_{frame:05d}.png"
        _image(path, seed)
        frames[fraction] = path
        outputs.append(str(path))
    (game / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "tv-royale-raw-cascade-v1",
                "replay": "replay-a",
                "arena": "arena_12",
                "frames": 101,
                "audit_outputs": outputs,
                "deduplication_frames": [
                    {"fraction": fraction, "path": str(path)}
                    for fraction, path in sorted(frames.items())
                ],
                "deck": ["hog_rider", "musketeer"],
            }
        ),
        encoding="utf-8",
    )
    run = tmp_path / "hf" / "run_manifest.json"
    run.write_text(
        json.dumps(
            {
                "dataset": "owner/private-permission-source",
                "records": [
                    {
                        "status": "complete",
                        "replay": "replay-a",
                        "arena": "arena_12",
                        "corpus": str(game / "corpus.npz"),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    split = tmp_path / "hf" / "split_manifest.json"
    split.write_text(
        json.dumps({"splits": {"train": {"replay_ids": ["replay-a"]}}}),
        encoding="utf-8",
    )
    return run, split, frames


def _youtube_fixture(
    tmp_path: Path,
    duplicate_frames: dict[float, Path],
    *,
    duplicate_split: str = "chronology_test",
) -> Path:
    videos = []
    for index in range(10):
        frame_rows = []
        for offset, fraction in enumerate((0.1, 0.5, 0.9)):
            path = tmp_path / f"yt-{index}-{offset}.png"
            if index == 0:
                path.write_bytes(duplicate_frames[fraction].read_bytes())
            else:
                _image(path, 100 + index * 3 + offset)
            frame_rows.append({"fraction": fraction, "path": str(path)})
        videos.append(
            {
                "id": f"video-{index}",
                "split": duplicate_split if index == 0 else "train",
                "duration_seconds": 10.1 if index == 0 else 20.0 + index,
                "players": ["Alpha", "Beta"] if index == 0 else [],
                "decks": [["Hog Rider", "Musketeer"]] if index == 0 else [],
                "frames": frame_rows,
            }
        )
    manifest = tmp_path / "youtube.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "tv-royale-youtube-canary-artifacts-v1",
                "permission_provenance": {
                    "basis": "creator_permission",
                    "ticket": "permission-123",
                },
                "videos": videos,
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_normalized_frame_hash_and_phash_are_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    _image(first, 7)
    second.write_bytes(first.read_bytes())

    first_fingerprint = fingerprint_frame(first)
    second_fingerprint = fingerprint_frame(second)

    assert first_fingerprint["normalized_frame_sha256"] == second_fingerprint[
        "normalized_frame_sha256"
    ]
    assert phash_distance(
        first_fingerprint["phash64"], second_fingerprint["phash64"]
    ) == 0


def test_unreviewed_candidate_is_atomic_and_quarantined(tmp_path: Path) -> None:
    run, split, frames = _hf_fixture(tmp_path)
    youtube = _youtube_fixture(tmp_path, frames)

    report = build_dedup_report(
        youtube_manifest=youtube,
        hf_run_manifests=[run],
        hf_split_manifest=split,
    )

    assert report["counts"]["candidate_pairs"] == 1
    assert report["counts"]["unresolved_candidate_pairs"] == 1
    candidate = report["candidate_pairs"][0]
    assert candidate["status"] == "candidate_needs_visual_confirmation"
    assert candidate["frame_evidence"]["exact_points"] == 3
    left = report["assignments"]["youtube:video-0"]
    right = report["assignments"]["huggingface:replay-a"]
    assert left["group_id"] == right["group_id"]
    assert left["atomic_split"] == "quarantine_dedup_review"
    assert report["invariants"]["dedup_group_cross_split_count"] == 0


def test_confirmed_duplicate_takes_one_protective_split(tmp_path: Path) -> None:
    run, split, frames = _hf_fixture(tmp_path)
    youtube = _youtube_fixture(tmp_path, frames)
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                "reviews": [
                    {
                        "left": "youtube:video-0",
                        "right": "huggingface:replay-a",
                        "visual_confirmation": "duplicate",
                        "reviewer": "fixture-reviewer",
                        "evidence": "same player, towers, and clock state",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_dedup_report(
        youtube_manifest=youtube,
        hf_run_manifests=[run],
        hf_split_manifest=split,
        review_manifest=review,
    )

    assert report["counts"]["confirmed_duplicate_pairs"] == 1
    assert report["candidate_pairs"][0]["status"] == "confirmed_duplicate"
    assert report["assignments"]["youtube:video-0"]["atomic_split"] == (
        "chronology_test"
    )
    assert report["assignments"]["huggingface:replay-a"]["atomic_split"] == (
        "chronology_test"
    )


def test_permission_provenance_is_preserved_not_called_cc(tmp_path: Path) -> None:
    run, split, frames = _hf_fixture(tmp_path)
    youtube = _youtube_fixture(tmp_path, frames)

    report = build_dedup_report(
        youtube_manifest=youtube,
        hf_run_manifests=[run],
        hf_split_manifest=split,
    )

    youtube_assignment = report["assignments"]["youtube:video-0"]
    assert youtube_assignment["permission_provenance"] == {
        "basis": "creator_permission",
        "ticket": "permission-123",
    }
    assert report["provenance"]["permission_provenance_preserved_not_relicensed"]
    assert report["invariants"]["permission_inferred_as_creative_commons"] is False


def test_hf_inventory_reports_missing_midpoint_without_faking_it(
    tmp_path: Path,
) -> None:
    run, split, frames = _hf_fixture(tmp_path)
    game_manifest = (
        tmp_path / "hf" / "games" / "arena_12" / "replay-a" / "manifest.json"
    )
    game = json.loads(game_manifest.read_text(encoding="utf-8"))
    game["deduplication_frames"] = [
        row for row in game["deduplication_frames"] if row["fraction"] != 0.5
    ]
    game_manifest.write_text(json.dumps(game), encoding="utf-8")

    inventory = inventory_hf_evidence([run], split_manifest=split)

    assert inventory["completed_records"] == 1
    assert inventory["game_manifests_found"] == 1
    assert inventory["complete_three_point_signatures"] == 0
    assert inventory["permission_provenance"]["creative_commons_license_claimed"] is False

    youtube = _youtube_fixture(tmp_path, frames)
    report = build_dedup_report(
        youtube_manifest=youtube,
        hf_run_manifests=[run],
        hf_split_manifest=split,
    )
    assert report["counts"]["hf_complete_three_point_artifacts"] == 0
    assert all(
        report["assignments"][f"youtube:video-{index}"]["atomic_split"]
        == "quarantine_incomplete_hf_index"
        for index in range(10)
    )
    assert report["invariants"][
        "youtube_training_eligible_only_with_complete_hf_index"
    ]
