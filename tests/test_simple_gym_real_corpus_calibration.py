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


def _corpus(
    tmp_path: Path,
    *,
    corrupt_hash: bool = False,
    match_name: str = "one",
    match_id: str = "youtube-one",
    vocabulary_sha: str = "b" * 64,
) -> Path:
    match = tmp_path / match_name
    match.mkdir(parents=True)
    neutral_rows: list[dict[str, Any]] = []
    for index in range(101):
        value = 2 if index < 30 else (1 if index < 60 else 120)
        neutral_rows.append(
            {
                "match_id": match_id,
                "snapshot_id": f"{match_id}-{index:06d}",
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
    actor_artifacts: list[dict[str, object]] = []
    for actor_id in (0, 1):
        actor_path = match / f"actor_{actor_id}.jsonl.gz"
        actor_sha = _write_jsonl_gz(
            actor_path,
            [
                {
                    "actor_id": actor_id,
                    "snapshot_id": f"{match_id}-000000",
                    "own_hud": {"hand": [], "elixir": {}},
                    "public_action_mask": {
                        "schema": "clasher.youtube.public_action_mask.v2",
                        "contract": "label_independent_public_action_mask_v2",
                        "contract_version": 2,
                        "legal_action_indices": [2304],
                        "non_noop_legal_actions": 0,
                        "valid": True,
                    },
                }
            ],
        )
        actor_artifacts.append(
            {
                "actor_id": actor_id,
                "neutral_join_key": "snapshot_id",
                "path": f"/copied/source/{actor_path.name}",
                "rows": 1,
                "sha256": actor_sha,
            }
        )
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
            "actor_trajectories": actor_artifacts,
        },
        "models": {"vocabulary_manifest_sha256": vocabulary_sha},
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
    assert channels["public_mask_v2"]["tensor_provider_available"] is True
    assert channels["public_mask_v2"]["actor_rows"] == 2
    assert (
        channels["public_mask_v2"][
            "actor_rows_joinable_to_neutral_public_state"
        ]
        == 2
    )
    assert channels["public_mask_v2"]["projection_mapping_complete"] is False
    assert channels["public_mask_v2"]["missing_mapping_requirements"] == [
        (
            "actor.global_features[11:13] Crown Tower alive/HP state is not "
            "serialized; the source builder confidence-gated tower-zone "
            "extensions, while the tensor provider interprets zero HP as destroyed"
        ),
        "manifests do not pin the tensor provider semantics_id",
        "manifests do not pin the tensor provider semantics_digest",
        "manifests do not pin the typed card/entity lookup_digest and card-data authority",
    ]
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
    assert integrity["errors"] == [
        f"{tmp_path.name}/one: neutral_sequence SHA-256 mismatch"
    ]


def test_complete_disjoint_additional_root_preserves_reset_denominator(
    tmp_path: Path,
) -> None:
    vocabulary = tmp_path / "vocabulary.json"
    vocabulary_sha = _write_json(vocabulary, {"entries": []})
    first = _corpus(
        tmp_path / "first",
        match_id="youtube-first",
        vocabulary_sha=vocabulary_sha,
    )
    second = _corpus(
        tmp_path / "second",
        match_id="youtube-second",
        vocabulary_sha=vocabulary_sha,
    )

    report = audit_real_corpus(
        first,
        _engine(),
        additional_roots=(second,),
        vocabulary_manifest=vocabulary,
    )

    assert report["corpus"]["matches"] == 2
    assert report["corpus"]["roots"] == [str(first.resolve()), str(second.resolve())]
    phase = report["channels"]["regulation_to_overtime_phase"]
    assert phase["successes"] == 2
    assert phase["total"] == 2
    assert "All manifests from every declared root" in phase["selection_policy"]
    mask = report["channels"]["public_mask_v2"]
    assert mask["verified_local_vocabulary_manifest_sha256"] == vocabulary_sha
    assert mask["manifests_with_vocabulary_sha256"] == 2


def test_markdown_names_blockers_and_cli_missing_root_fails(tmp_path: Path) -> None:
    report = audit_real_corpus(_corpus(tmp_path / "corpus"), _engine())
    markdown = render_markdown(report)
    assert "Decision: `insufficient_evidence`" in markdown
    assert "1 regulation-to-overtime resets" in markdown
    assert "tensor public-mask-v2 provider is callable" in markdown
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
