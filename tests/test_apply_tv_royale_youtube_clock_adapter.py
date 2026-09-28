import gzip
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.apply_tv_royale_youtube_clock_adapter import (
    ANCHOR_SCHEMA,
    apply_clock_anchors,
    load_anchors,
    portable_path,
)


def test_clock_anchor_contract_is_current_frame_only_and_stride_aligned(
    tmp_path: Path,
) -> None:
    path = tmp_path / "anchors.jsonl"
    rows = [
        {
            "schema": ANCHOR_SCHEMA,
            "output_pts": 0,
            "seconds_remaining": 180,
            "confidence": 0.9,
            "raw_text": ["3:00"],
            "current_frame_only": True,
        },
        {
            "schema": ANCHOR_SCHEMA,
            "output_pts": 5,
            "seconds_remaining": 179,
            "confidence": 0.8,
            "raw_text": ["2:59"],
            "current_frame_only": True,
        },
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert sorted(load_anchors(path, stride=5)) == [0, 5]

    rows[1]["current_frame_only"] = False
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid current-frame"):
        load_anchors(path, stride=5)


def test_apply_clock_anchors_preserves_pts_and_fails_closed_when_missing(
    tmp_path: Path,
) -> None:
    neutral = tmp_path / "neutral.jsonl.gz"
    with gzip.open(neutral, "wt", encoding="utf-8") as output:
        for pts in range(6):
            output.write(
                json.dumps(
                    {
                        "output_pts": pts,
                        "timestamp_ms": pts * 100,
                        "public": {"clock": {"valid": False}},
                    }
                )
                + "\n"
            )
    events = tmp_path / "events.json"
    events.write_text("[]\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": {
                    "neutral_sequence": {"path": str(neutral), "rows": 6},
                    "actor_trajectories": [{"path": "old"}],
                    "offline_play_events": {"path": str(events), "rows": 0},
                },
                "coverage": {"clock_valid_frames": 0},
                "models": {"clock_head": {"anchor_stride_frames": 5}},
                "limitations": ["clock head is deferred"],
            }
        ),
        encoding="utf-8",
    )
    anchors = tmp_path / "anchors.jsonl"
    anchors.write_text(
        json.dumps(
            {
                "schema": ANCHOR_SCHEMA,
                "output_pts": 0,
                "seconds_remaining": 180,
                "confidence": 0.9,
                "raw_text": ["3:00"],
                "current_frame_only": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "clocked"
    result = apply_clock_anchors(
        input_manifest=manifest,
        anchors_path=anchors,
        output_dir=output_dir,
        provider_path=tmp_path / "provider",
        provider_sha256="a" * 64,
    )
    assert result["coverage"]["clock_valid_frames"] == 5
    assert result["artifacts"]["actor_trajectories"] == []
    with gzip.open(result["artifacts"]["neutral_sequence"]["path"], "rt") as source:
        rows = [json.loads(line) for line in source]
    assert [row["output_pts"] for row in rows] == list(range(6))
    assert all(rows[index]["public"]["clock"]["valid"] for index in range(5))
    assert rows[5]["public"]["clock"]["valid"] is False


def test_pinned_portable_provider_matches_launcher_interface() -> None:
    provider = Path("tools/recognize_public_clock.py")
    assert provider.stat().st_mode & 0o111
    assert (
        hashlib.sha256(provider.read_bytes()).hexdigest()
        == "3449258cca75784926206ffabb87eacd8f9d8f247e6ca993c8d3d761e36f1b39"
    )
    help_text = subprocess.run(
        [str(provider), "--help"], check=True, capture_output=True, text=True
    ).stdout
    for option in (
        "--source-video",
        "--source-manifest",
        "--output-jsonl",
        "--sample-hz",
        "--anchor-stride-frames",
    ):
        assert option in help_text
    anchors = Path(
        "datasets/derived/tv_royale_portable_clock_hTG8dM4KtM4_20260817/clock_anchors.jsonl"
    )
    assert len(load_anchors(anchors, stride=5)) == 535


def test_clock_publication_manifest_uses_final_atomic_paths(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    neutral = input_dir / "neutral.jsonl.gz"
    with gzip.open(neutral, "wt", encoding="utf-8") as output:
        output.write(
            json.dumps(
                {
                    "output_pts": 0,
                    "timestamp_ms": 0,
                    "public": {"clock": {"valid": False}},
                }
            )
            + "\n"
        )
    events = input_dir / "events.json"
    events.write_text("[]\n", encoding="utf-8")
    manifest = input_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": {
                    "neutral_sequence": {"path": str(neutral)},
                    "offline_play_events": {"path": str(events), "rows": 0},
                },
                "models": {"clock_head": {"anchor_stride_frames": 5}},
                "coverage": {},
                "limitations": [],
            }
        ),
        encoding="utf-8",
    )
    anchors = input_dir / "anchors.jsonl"
    anchors.write_text(
        json.dumps(
            {
                "schema": ANCHOR_SCHEMA,
                "current_frame_only": True,
                "output_pts": 0,
                "seconds_remaining": 180,
                "confidence": 1.0,
                "raw_text": ["3:00"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    final = tmp_path / "final"
    result = apply_clock_anchors(
        input_manifest=manifest,
        anchors_path=anchors,
        output_dir=final,
        provider_path=tmp_path / "provider",
        provider_sha256="a" * 64,
    )
    assert Path(result["artifacts"]["neutral_sequence"]["path"]) == (
        final / "neutral_sequence_clocked.jsonl.gz"
    )
    assert (final / "manifest.json").is_file()
    assert not list(tmp_path.glob(".final.*.partial"))


def test_portable_path_is_relative_only_inside_current_checkout(tmp_path: Path) -> None:
    inside = Path.cwd() / "datasets" / "derived" / "example.json"
    assert portable_path(inside) == "datasets/derived/example.json"
    assert portable_path(tmp_path / "external.json") == str(tmp_path / "external.json")
