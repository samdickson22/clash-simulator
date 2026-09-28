from __future__ import annotations

import gzip
import json
from pathlib import Path

from scripts.verify_tv_royale_youtube_fullmatch_contract import (
    ACTOR_SCHEMA,
    MANIFEST_SCHEMA,
    NEUTRAL_SCHEMA,
    NOOP_ACTION,
    file_sha256,
    verify,
)


def _head(value: object, *, valid: bool = True) -> dict[str, object]:
    return {
        "value": value if valid else None,
        "candidate": value,
        "confidence": 0.9,
        "valid": valid,
        "reason": None if valid else "missing",
    }


def _hud(card: str) -> dict[str, object]:
    return {
        "hand": [_head(card) for _ in range(4)],
        "next_card": _head(card),
        "elixir": _head(5),
        "all_hand_valid": True,
        "complete_valid": True,
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, sort_keys=True) + "\n")


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    extraction = tmp_path / "semantic"
    extraction.mkdir()
    source_video = tmp_path / "source.webm"
    source_video.write_bytes(b"video")
    source_manifest = tmp_path / "source_manifest.json"
    source_manifest.write_text(
        json.dumps(
            {
                "source_media": {
                    "path": str(source_video),
                    "sha256": file_sha256(source_video),
                "source_time_base": "1/1000",
                "probed_duration_seconds": 0.1,
                },
                "decode": {"sample_count": 1, "output_time_base": "1/10"},
            }
        )
    )
    entity = {
        "visual_class": "rocket",
        "team_id": 0,
        "confidence": 0.9,
        "identity": {"stable_key": "projectile:Rocket", "valid": True},
        "hp_valid": True,
        "hp_confidence": 0.8,
        "status": _head("flying"),
        "projectile_target": _head([9.0, 20.0]),
    }
    tower = {
        **entity,
        "visual_class": "king-tower",
        "identity": {"stable_key": "tower:KingTower", "valid": True},
    }
    effect = {
        **entity,
        "visual_class": "freeze",
        "identity": {"stable_key": "area_effect:Freeze", "valid": True},
    }
    neutral = {
        "schema": NEUTRAL_SCHEMA,
        "match_id": "youtube-test",
        "split_group_id": "youtube-test",
        "snapshot_id": "youtube-test-000000",
        "sample_index": 0,
        "output_pts": 0,
        "output_time_base": "1/10",
        "source_time_base": "1/1000",
        "timestamp_ms": 0,
        "source_timing": {
            "decoded_sample_index": 0,
            "output_pts": 0,
            "output_time_base": "1/10",
            "source_time_base": "1/1000",
            "target_source_time_seconds": 0.0,
        },
        "public": {
            "coordinate_frame": "absolute_world",
            "clock": _head(180),
            "entities": [entity, tower, effect],
        },
        "offline_privileged_hud": {"0": _hud("Knight"), "1": _hud("Arrows")},
        "offline_evidence": {
            "play_events": [],
            "simulator_state_used": False,
            "exact_simulator_action_mask_used": False,
        },
    }
    neutral_path = extraction / "neutral.jsonl.gz"
    _write_jsonl(neutral_path, [neutral])
    actor_rows = []
    for actor_id in (0, 1):
        actor = {
            "schema": ACTOR_SCHEMA,
            "match_id": neutral["match_id"],
            "split_group_id": neutral["split_group_id"],
            "snapshot_id": neutral["snapshot_id"],
            "output_pts": 0,
            "output_time_base": "1/10",
            "source_time_base": "1/1000",
            "timestamp_ms": neutral["timestamp_ms"],
            "actor_id": actor_id,
            "public": neutral["public"],
            "own_hud": neutral["offline_privileged_hud"][str(actor_id)],
            "public_action_mask": {
                "contract": "label_independent_public_v1",
                "legal_action_indices": [0, NOOP_ACTION],
                "valid": True,
            },
        }
        path = extraction / f"actor_{actor_id}.jsonl.gz"
        _write_jsonl(path, [actor])
        actor_rows.append((actor_id, path))
    events = [
        {
            "play_valid": True,
            "placement_valid": True,
            "identity_valid": True,
            "card_identity": "Knight",
            "deployment_tile": [9, 10],
        }
    ]
    event_path = extraction / "events.json"
    event_path.write_text(json.dumps(events))
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "source": {
            "video_sha256": file_sha256(source_video),
            "acquisition_manifest_sha256": file_sha256(source_manifest),
        },
        "artifacts": {
            "neutral_sequence": {
                "path": str(neutral_path),
                "sha256": file_sha256(neutral_path),
                "rows": 1,
            },
            "actor_trajectories": [
                {
                    "actor_id": actor_id,
                    "path": str(path),
                    "sha256": file_sha256(path),
                    "rows": 1,
                }
                for actor_id, path in actor_rows
            ],
            "offline_play_events": {
                "path": str(event_path),
                "sha256": file_sha256(event_path),
                "rows": 1,
            },
        },
        "timing_seconds": {
            "model_load": 1.0,
            "video_decode": 1.0,
            "hud_current_frame_matching": 1.0,
            "arena_detector": 1.0,
            "serialization_and_other": 1.0,
            "total_wall": 5.0,
        },
        "resources": {"max_rss_bytes": 1024},
        "sampling": {"decoded_source_frames": 1},
        "leakage_contract": {
            "raw_frames_in_actor_artifacts": 0,
            "opponent_hud_in_actor_artifacts": 0,
            "simulator_state_inputs": 0,
            "exact_simulator_masks": 0,
            "event_labels_are_offline_only": True,
            "public_masks_depend_on_labels": False,
            "same_split_group_for_both_actors": True,
        },
    }
    (extraction / "manifest.json").write_text(json.dumps(manifest))
    return extraction, source_manifest


def test_complete_fixture_passes_every_gate(tmp_path: Path) -> None:
    extraction, source_manifest = _fixture(tmp_path)
    report = verify(
        extraction_dir=extraction, source_manifest_path=source_manifest
    )
    assert report["status"] == "passed"
    assert report["failed_gates"] == []


def test_missing_pts_and_cross_actor_hud_leak_fail_closed(tmp_path: Path) -> None:
    extraction, source_manifest = _fixture(tmp_path)
    neutral_path = extraction / "neutral.jsonl.gz"
    with gzip.open(neutral_path, "rt", encoding="utf-8") as source:
        neutral = next(json.loads(line) for line in source)
    neutral.pop("source_timing")
    neutral.pop("output_pts")
    neutral.pop("output_time_base")
    neutral.pop("source_time_base")
    _write_jsonl(neutral_path, [neutral])
    manifest_path = extraction / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"]["neutral_sequence"]["sha256"] = file_sha256(neutral_path)
    manifest_path.write_text(json.dumps(manifest))
    actor_path = extraction / "actor_0.jsonl.gz"
    with gzip.open(actor_path, "rt", encoding="utf-8") as source:
        actor = next(json.loads(line) for line in source)
    actor["opponent_hud"] = _hud("Arrows")
    _write_jsonl(actor_path, [actor])
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"]["actor_trajectories"][0]["sha256"] = file_sha256(
        actor_path
    )
    manifest_path.write_text(json.dumps(manifest))
    report = verify(
        extraction_dir=extraction, source_manifest_path=source_manifest
    )
    assert "published_pts_and_timebase_lineage" in report["failed_gates"]
    assert "no_future_simulator_or_opponent_leakage" in report["failed_gates"]


def test_all_noop_masks_fail_nontrivial_coverage_gate(tmp_path: Path) -> None:
    extraction, source_manifest = _fixture(tmp_path)
    manifest_path = extraction / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for actor_id in (0, 1):
        actor_path = extraction / f"actor_{actor_id}.jsonl.gz"
        with gzip.open(actor_path, "rt", encoding="utf-8") as source:
            actor = next(json.loads(line) for line in source)
        actor["public_action_mask"]["legal_action_indices"] = [NOOP_ACTION]
        _write_jsonl(actor_path, [actor])
        manifest["artifacts"]["actor_trajectories"][actor_id]["sha256"] = (
            file_sha256(actor_path)
        )
    manifest_path.write_text(json.dumps(manifest))
    report = verify(
        extraction_dir=extraction, source_manifest_path=source_manifest
    )
    assert "nontrivial_masks_on_complete_hud_elixir_rows" in report["failed_gates"]
