from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from scripts.calibrate_simple_gym_real_corpus import (
    CALIBRATION_SCHEMA,
    EngineCalibrationContract,
    audit_real_corpus,
    main,
    render_markdown,
)


def _write_json(path: Path, value: object) -> str:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl_gz(path: Path, rows: list[dict[str, Any]]) -> str:
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _engine() -> EngineCalibrationContract:
    return EngineCalibrationContract(
        manifest_path="fixture-engine.json",
        manifest_sha256="a" * 64,
        supported_public_cards=("Knight",),
        stable_action_keys=frozenset(("card_action:Knight",)),
        canonical_lane_globals=True,
        public_mask_contract_version=2,
        logic_tick_ms=50,
        regulation_ticks=3600,
        tiebreak_ticks=6000,
    )


def _corpus(tmp_path: Path, *, corrupt_hash: bool = False) -> Path:
    match = tmp_path / "one"
    match.mkdir(parents=True)
    neutral_rows: list[dict[str, Any]] = []
    for index in range(101):
        value = 2 if index < 30 else (1 if index < 60 else 120)
        neutral_rows.append(
            {
                "match_id": "youtube-one",
                "timestamp_ms": 174_000 + index * 100,
                "public": {
                    "coordinate_frame": "absolute_world",
                    "clock": {"valid": True, "value": value},
                },
            }
        )
    neutral_sha = _write_jsonl_gz(match / "neutral.jsonl.gz", neutral_rows)
    targets = [
        {
            "actor_id": index % 2,
            "card_identity": "card_action:Knight",
            "deployment_tile_actor_canonical": [9, 10],
            "expert_action": 10 * 18 + 9,
            "expert_action_in_public_mask": True,
            "hand_slot": 0,
        }
        for index in range(100)
    ]
    target_sha = _write_json(match / "targets.json", targets)
    events = [
        {
            "card_identity": "card_action:Knight",
            "deployment_tile_absolute": [8, 21] if index % 2 else [9, 10],
            "deployment_tile_actor_canonical": [9, 10],
            "deployment_world_position": ([8.5, 21.5] if index % 2 else [9.5, 10.5]),
            "play_valid": True,
            "player_id": index % 2,
            "timestamp_ms": index * 100,
        }
        for index in range(100)
    ]
    event_sha = _write_json(match / "events.json", events)
    manifest = {
        "artifacts": {
            "neutral_sequence": {
                "path": "/copied/source/neutral.jsonl.gz",
                "rows": len(neutral_rows),
                "sha256": "0" * 64 if corrupt_hash else neutral_sha,
            },
            "offline_actor_targets": {
                "path": "/copied/source/targets.json",
                "rows": len(targets),
                "sha256": target_sha,
            },
            "offline_play_events": {
                "path": "/copied/source/events.json",
                "rows": len(events),
                "sha256": event_sha,
            },
        },
        "public_mask_v3": {
            "contract": "label_independent_public_action_mask_v2",
            "contract_version": 2,
            "exact_simulator_state_used": False,
            "label_independent": True,
        },
        "sampling": {"output_time_base": "1/10"},
    }
    _write_json(match / "manifest.json", manifest)
    return tmp_path


def test_bounded_channels_pass_but_single_phase_reset_is_insufficient(
    tmp_path: Path,
) -> None:
    report = audit_real_corpus(_corpus(tmp_path), _engine())

    assert report["schema"] == CALIBRATION_SCHEMA
    assert report["decision"] == "insufficient_evidence"
    channels = report["channels"]
    assert channels["artifact_integrity"]["status"] == "pass"
    assert channels["sampling_100ms"]["status"] == "pass"
    assert channels["typed_action_identity"]["status"] == "pass"
    assert channels["hand_slot_action_encoding"]["status"] == "pass"
    assert channels["canonical_orientation"]["status"] == "pass"
    assert channels["coarse_placement_encoding"]["status"] == "pass"
    assert channels["regulation_to_overtime_phase"]["status"] == (
        "insufficient_evidence"
    )
    assert channels["public_mask_v2"]["status"] == "contract_only"
    assert channels["public_mask_v2"]["engine_equivalence"] == "unavailable"
    assert set(report["unavailable_channels"]) >= {
        "exact_hp_and_damage",
        "projectile_source_target_and_flight",
        "status_onset_and_duration",
        "outcomes",
    }


def test_hash_mismatch_fails_integrity_without_upgrading_other_channels(
    tmp_path: Path,
) -> None:
    report = audit_real_corpus(_corpus(tmp_path, corrupt_hash=True), _engine())
    assert report["decision"] == "fail"
    integrity = report["channels"]["artifact_integrity"]
    assert integrity["status"] == "fail"
    assert integrity["errors"] == ["one: neutral_sequence SHA-256 mismatch"]


def test_markdown_names_blockers_and_cli_missing_root_fails(tmp_path: Path) -> None:
    report = audit_real_corpus(_corpus(tmp_path / "corpus"), _engine())
    markdown = render_markdown(report)
    assert "Decision: `insufficient_evidence`" in markdown
    assert "1 regulation-to-overtime resets" in markdown
    assert "no callable real-frame mask adapter" in markdown
    assert (
        "does not calibrate HP/damage, projectiles, statuses, or outcomes" in markdown
    )

    output = io.StringIO()
    errors = io.StringIO()
    code = main(
        [str(tmp_path / "missing"), "--engine-manifest", str(tmp_path / "none")],
        stdout=output,
        stderr=errors,
    )
    assert code == 2
    assert output.getvalue() == ""
    assert "cannot read JSON" in errors.getvalue()
