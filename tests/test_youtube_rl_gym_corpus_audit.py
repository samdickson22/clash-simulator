from __future__ import annotations

import gzip
import io
import json
from pathlib import Path
from typing import Any, cast

import pytest

from scripts.audit_youtube_rl_gym_corpus import (
    AUDIT_SCHEMA,
    CorpusAuditError,
    audit_corpus,
    main,
)


def _entity(
    *,
    identity: bool,
    hp: bool,
    position: list[float] | None,
    confidence: float,
) -> dict[str, Any]:
    return {
        "confidence": confidence,
        "hp_valid": hp,
        "identity": {"valid": identity},
        "projectile_target": {
            "valid": False,
            "reason": "no_projectile_target_head",
        },
        "status": {"valid": False, "reason": "no_calibrated_status_head"},
        "world_position": position,
    }


def _frame(
    match_id: str,
    index: int,
    *,
    clock: bool,
    entities: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "match_id": match_id,
        "public": {
            "clock": {"valid": clock},
            "coordinate_frame": "absolute_world",
            "entities": entities,
        },
        "snapshot_id": f"{match_id}-{index:06d}",
    }


def _write_match(
    root: Path,
    directory: str,
    frames: list[dict[str, Any]],
    *,
    coverage: dict[str, int],
    action_target_rows: int,
    compressed: bool,
) -> None:
    match_root = root / directory
    match_root.mkdir(parents=True)
    filename = "neutral_sequence.jsonl.gz" if compressed else "neutral_sequence.jsonl"
    sequence_path = match_root / filename
    if compressed:
        with gzip.open(sequence_path, "wt", encoding="utf-8") as stream:
            for frame in frames:
                stream.write(json.dumps(frame, sort_keys=True) + "\n")
    else:
        with sequence_path.open("w", encoding="utf-8") as stream:
            for frame in frames:
                stream.write(json.dumps(frame, sort_keys=True) + "\n")
    manifest = {
        "artifacts": {
            "actor_trajectories": [
                {"actor_id": 0, "rows": len(frames)},
                {"actor_id": 1, "rows": len(frames)},
            ],
            "neutral_sequence": {
                # An intentionally stale absolute parent proves root relocation
                # resolves the manifest artifact by local basename.
                "path": f"/stale/export/{directory}/{filename}",
                "rows": len(frames),
            },
            "offline_actor_targets": {"rows": action_target_rows},
        },
        "coverage": coverage,
    }
    (match_root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )


@pytest.fixture
def corpus_root(tmp_path: Path) -> Path:
    first = [
        _frame(
            "youtube-a",
            0,
            clock=True,
            entities=[
                _entity(identity=True, hp=True, position=[1.0, 2.0], confidence=0.8),
                _entity(identity=False, hp=False, position=None, confidence=0.4),
            ],
        ),
        _frame(
            "youtube-a",
            1,
            clock=False,
            entities=[
                _entity(identity=True, hp=False, position=[2.0, 3.0], confidence=0.6)
            ],
        ),
    ]
    second = [
        _frame(
            "youtube-b",
            0,
            clock=True,
            entities=[
                _entity(identity=False, hp=True, position=[3.0, 4.0], confidence=0.9)
            ],
        )
    ]
    _write_match(
        tmp_path,
        "a",
        first,
        coverage={
            "clock_valid_frames": 1,
            "detections": 3,
            "hp_valid": 1,
            "play_event_identity_valid": 1,
            "play_event_placement_valid": 2,
            "play_events": 3,
            "play_events_valid": 1,
            "projectile_target_valid": 0,
            "status_valid": 0,
            "typed_identity_valid": 2,
        },
        action_target_rows=1,
        compressed=True,
    )
    _write_match(
        tmp_path,
        "b",
        second,
        coverage={
            "clock_valid_frames": 1,
            "detections": 1,
            "hp_valid": 1,
            "play_event_identity_valid": 1,
            "play_event_placement_valid": 2,
            "play_events": 2,
            "play_events_valid": 1,
            "projectile_target_valid": 0,
            "status_valid": 0,
            "typed_identity_valid": 0,
        },
        action_target_rows=2,
        compressed=False,
    )
    return tmp_path


def test_audit_summarizes_rl_gym_coverage_and_unavailable_targets(
    corpus_root: Path,
) -> None:
    before = sorted(path.relative_to(corpus_root) for path in corpus_root.rglob("*"))

    report = cast(dict[str, Any], audit_corpus(corpus_root))

    after = sorted(path.relative_to(corpus_root) for path in corpus_root.rglob("*"))
    assert after == before
    assert report["schema"] == AUDIT_SCHEMA
    assert report["matches"] == {"directories": 2, "distinct_match_ids": 2}
    assert report["frames"] == {
        "observed": 3,
        "manifest_declared": 3,
        "actor_overlay_rows": 6,
    }
    entities = report["entities"]
    assert isinstance(entities, dict)
    assert entities["detections"] == 4
    assert entities["typed_identity"] == {
        "availability": "available",
        "valid": 2,
        "total": 4,
        "rate": 0.5,
    }
    assert entities["hp"]["valid"] == 2
    assert entities["position"]["valid"] == 3
    assert entities["position"]["rate"] == 0.75
    assert entities["position"]["coordinate_frames"] == {"absolute_world": 3}
    assert entities["position"]["resolved_confidence"] == {
        "count": 3,
        "minimum": 0.6,
        "p10": 0.64,
        "median": 0.8,
        "p90": 0.88,
        "maximum": 0.9,
        "mean": 0.766667,
    }
    assert entities["status_targets"]["availability"] == "unavailable"
    assert entities["status_targets"]["unavailable_reasons"] == {
        "no_calibrated_status_head": 4
    }
    assert entities["projectile_targets"]["availability"] == "unavailable"
    assert entities["projectile_targets"]["unavailable_reasons"] == {
        "no_projectile_target_head": 4
    }
    assert report["clock"]["valid"] == 2
    assert report["clock"]["rate"] == 0.666667
    assert report["actions"] == {
        "offline_only": True,
        "events": 5,
        "complete_identity_and_placement": {
            "availability": "available",
            "valid": 2,
            "total": 5,
            "rate": 0.4,
        },
        "typed_identity": {
            "availability": "available",
            "valid": 2,
            "total": 5,
            "rate": 0.4,
        },
        "placement": {
            "availability": "available",
            "valid": 4,
            "total": 5,
            "rate": 0.8,
        },
        "actor_training_targets": 3,
    }
    assert report["integrity"] == {
        "frame_row_mismatches": [],
        "manifest_counter_mismatches": {},
        "clean": True,
    }


def test_markdown_and_json_cli_outputs_are_concise(corpus_root: Path) -> None:
    markdown = io.StringIO()
    errors = io.StringIO()
    assert (
        main(
            [str(corpus_root), "--format", "markdown"],
            stdout=markdown,
            stderr=errors,
        )
        == 0
    )
    rendered = markdown.getvalue()
    assert "29" not in rendered
    assert "Matches: 2 directories / 2 distinct IDs" in rendered
    assert "Entity status target | 0 | 4 | 0.00% | unavailable" in rendered
    assert "Projectile target | 0 | 4 | 0.00% | unavailable" in rendered
    assert "Action labels are offline-only" in rendered
    assert errors.getvalue() == ""

    output = io.StringIO()
    assert main([str(corpus_root)], stdout=output, stderr=errors) == 0
    assert json.loads(output.getvalue())["schema"] == AUDIT_SCHEMA


def test_integrity_mismatches_are_reported_not_hidden(corpus_root: Path) -> None:
    manifest_path = corpus_root / "a" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["coverage"]["hp_valid"] = 9
    manifest["artifacts"]["neutral_sequence"]["rows"] = 99
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = cast(dict[str, Any], audit_corpus(corpus_root))

    assert report["integrity"]["clean"] is False
    assert report["integrity"]["manifest_counter_mismatches"] == {
        "hp_valid": {"manifest": 10, "observed": 2}
    }
    assert report["integrity"]["frame_row_mismatches"] == [
        {"match_directory": "a", "declared": 99, "observed": 2}
    ]


def test_absent_root_and_missing_argument_fail_clearly(tmp_path: Path) -> None:
    missing = tmp_path / "not-there"
    with pytest.raises(CorpusAuditError, match="corpus root does not exist"):
        audit_corpus(missing)

    output = io.StringIO()
    errors = io.StringIO()
    assert main([str(missing)], stdout=output, stderr=errors) == 2
    assert output.getvalue() == ""
    assert errors.getvalue() == f"error: corpus root does not exist: {missing}\n"

    with pytest.raises(SystemExit) as exit_info:
        main([], stdout=output, stderr=errors)
    assert exit_info.value.code == 2


def test_empty_or_malformed_root_fails_with_artifact_context(tmp_path: Path) -> None:
    with pytest.raises(CorpusAuditError, match="contains no match manifests"):
        audit_corpus(tmp_path)

    match = tmp_path / "bad"
    match.mkdir()
    (match / "manifest.json").write_text(
        json.dumps({"artifacts": {}, "coverage": {}}), encoding="utf-8"
    )
    with pytest.raises(
        CorpusAuditError,
        match="artifacts.neutral_sequence must be a JSON object",
    ):
        audit_corpus(tmp_path)
