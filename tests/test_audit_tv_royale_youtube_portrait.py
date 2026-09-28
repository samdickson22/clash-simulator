from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from scripts.audit_tv_royale_youtube_portrait import (
    ACTOR_PROJECTION_SCHEMA,
    BOTTOM_ACTOR_ARENA_BOX,
    BOTTOM_ACTOR_EXPORT_SCHEMA,
    INPUT_SCHEMA,
    NEUTRAL_SNAPSHOT_SCHEMA,
    OFFLINE_LABEL_ONLY_SCHEMA,
    PERMISSION_BASIS,
    PRODUCTION_ARTIFACT_SCHEMA,
    SPECTATOR_LAYOUT_2_16,
    ActorArtifactContractError,
    NeutralProjectionContractError,
    RejectReason,
    audit_canary,
    build_neutral_extraction_readiness,
    detect_layout,
    export_bottom_actor_canary,
    project_neutral_snapshot,
    render_audit,
    validate_actor_projection,
    validate_production_artifact_reference,
)


def _portrait_frame() -> np.ndarray:
    image = np.full((1280, 592, 3), (95, 145, 175), dtype=np.uint8)
    # Visible local-player elixir band within the declared HUD-relative region.
    cv2.rectangle(image, (190, 1165), (565, 1195), (185, 30, 180), -1)
    return image


def _spectator_frame() -> np.ndarray:
    image = np.full((1280, 592, 3), (95, 145, 175), dtype=np.uint8)
    cv2.rectangle(image, (8, 35), (560, 90), (185, 30, 180), -1)
    cv2.rectangle(image, (8, 1165), (560, 1245), (185, 30, 180), -1)
    return image


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canary(tmp_path: Path, image: np.ndarray) -> Path:
    frame = tmp_path / "frame.png"
    assert cv2.imwrite(str(frame), image)
    payload = {
        "schema": INPUT_SCHEMA,
        "permission_provenance": {
            "basis": PERMISSION_BASIS,
            "public_cc_license_claimed": False,
        },
        "videos": [
            {
                "id": "abcdefghijk",
                "sections": [
                    {
                        "label": "p50",
                        "frames": [{"path": frame.name, "sha256": _sha(frame)}],
                    }
                ],
            }
        ],
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


def test_detects_native_portrait_geometry_and_normalizes_exact_grid() -> None:
    image = _portrait_frame()

    detected, reason, metrics = detect_layout(image)

    assert reason is None
    assert detected is not None
    assert detected.layout.name == "live_portrait_2.16"
    assert len(detected.hand_pixels) == 4
    assert metrics["hud_purple_fraction"] > 0.01
    rendered = render_audit(
        image,
        detected,
        {
            "sprite_boxes": [{"box": [0.2, 0.3, 0.3, 0.5], "label": "Knight"}],
            "deployment_points": [{"x": 0.25, "y": 0.75, "card": "Knight"}],
            "events": [{"x": 0.25, "y": 0.75, "label": "own_play"}],
            "statuses": [{"x": 0.6, "y": 0.4, "label": "slow"}],
        },
    )
    assert rendered.shape[0] == image.shape[0]
    assert rendered.shape[1] > image.shape[1]


@pytest.mark.parametrize(
    ("image", "reason"),
    [
        (np.zeros((400, 800, 3), dtype=np.uint8), RejectReason.UNSUPPORTED_ORIENTATION),
        (np.zeros((1280, 592, 3), dtype=np.uint8), RejectReason.EXCESSIVE_LETTERBOX),
        (np.full((1000, 592, 3), 100, dtype=np.uint8), RejectReason.AMBIGUOUS_LAYOUT),
    ],
)
def test_fails_closed_on_orientation_letterbox_and_unknown_geometry(
    image: np.ndarray, reason: RejectReason
) -> None:
    detected, actual, _ = detect_layout(image)
    assert detected is None
    assert actual == reason


def test_rejects_spectator_view_without_local_elixir_hud() -> None:
    image = np.full((1280, 592, 3), 120, dtype=np.uint8)
    detected, reason, _ = detect_layout(image)
    assert detected is None
    assert reason == RejectReason.SPECTATOR_UI_OR_MISSING_LOCAL_HUD


def test_detects_dual_hud_spectator_leak_and_still_renders_quarantine_grid() -> None:
    image = _spectator_frame()

    detected, reason, metrics = detect_layout(image)

    assert detected is not None
    assert detected.layout.name == "spectator_portrait_2.16"
    assert reason == RejectReason.SPECTATOR_UI_OR_MISSING_LOCAL_HUD
    assert metrics["spectator_top_purple_fraction"] > 0.008
    assert metrics["spectator_bottom_purple_fraction"] > 0.008
    assert render_audit(image, detected).shape[1] > image.shape[1]


def test_manifest_requires_manual_review_and_pins_exact_hashes(tmp_path: Path) -> None:
    manifest = _canary(tmp_path, _portrait_frame())
    output = tmp_path / "audit"

    pending = audit_canary(canary_manifest=manifest, output_directory=output)

    assert pending["accepted"] is False
    assert pending["records"][0]["reject_reason"] == RejectReason.MANUAL_REVIEW_REQUIRED
    assert len(pending["records"][0]["source_sha256"]) == 64
    assert len(pending["records"][0]["rendered_sha256"]) == 64
    manifest_digest = _sha(output / "manifest.json")
    assert (output / "manifest.sha256").read_text(encoding="ascii") == (
        f"{manifest_digest}  manifest.json\n"
    )
    assert pending["replacement_gate_evidence"]["hud_frames"] == {
        "audited": 1,
        "minimum": 300,
        "result": "insufficient_evidence",
    }
    key = pending["records"][0]["key"]
    reviews = tmp_path / "reviews.json"
    reviews.write_text(
        json.dumps(
            {
                key: {
                    "decision": "accept",
                    "reviewer": "visual-qa-test",
                    "grid_aligned": True,
                    "clock_region_correct": True,
                    "hand_next_elixir_regions_correct": True,
                    "sprite_boxes_are_not_hitboxes": True,
                    "deployment_overlay_correct": True,
                    "status_overlay_correct": True,
                    "notes": "synthetic fixture",
                }
            }
        ),
        encoding="utf-8",
    )

    accepted = audit_canary(
        canary_manifest=manifest,
        output_directory=output,
        reviews_path=reviews,
    )
    assert accepted["accepted"] is True
    assert accepted["records"][0]["reject_reason"] is None


def test_permission_is_explicitly_not_creative_commons(tmp_path: Path) -> None:
    manifest = _canary(tmp_path, _portrait_frame())
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["permission_provenance"]["public_cc_license_claimed"] = True
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="public_cc_license_claimed=false"):
        audit_canary(canary_manifest=manifest, output_directory=tmp_path / "audit")


def test_manual_caption_rejection_is_typed(tmp_path: Path) -> None:
    manifest = _canary(tmp_path, _portrait_frame())
    pending = audit_canary(
        canary_manifest=manifest, output_directory=tmp_path / "audit"
    )
    key = pending["records"][0]["key"]
    reviews = tmp_path / "reviews.json"
    reviews.write_text(
        json.dumps(
            {
                key: {
                    "decision": "reject",
                    "reject_reason": RejectReason.CAPTIONS_OVER_ARENA,
                    "reviewer": "visual-qa-test",
                    "notes": "synthetic caption overlap",
                }
            }
        ),
        encoding="utf-8",
    )

    rejected = audit_canary(
        canary_manifest=manifest,
        output_directory=tmp_path / "audit",
        reviews_path=reviews,
    )
    assert rejected["records"][0]["reject_reason"] == "captions_over_arena"


def test_bottom_actor_export_physically_separates_private_top_hud(
    tmp_path: Path,
) -> None:
    manifest = _canary(tmp_path, _spectator_frame())
    output = tmp_path / "actor"

    payload = export_bottom_actor_canary(
        canary_manifest=manifest, output_directory=output
    )

    assert payload["schema"] == BOTTOM_ACTOR_EXPORT_SCHEMA
    assert payload["accepted"] == 1
    assert payload["rejected"] == 0
    record = payload["records"][0]
    assert record["offline_label_only"]["schema"] == OFFLINE_LABEL_ONLY_SCHEMA
    assert record["offline_label_only"]["inference_eligible"] is False
    assert record["offline_label_only"]["path"].startswith("offline_label_only/")
    assert all(
        reference["path"].startswith("production/")
        for reference in record["production"].values()
    )
    assert all(
        "offline_label_only" not in reference["path"]
        for reference in record["model_pixel_inputs"]
    )
    arena = cv2.imread(str(output / record["production"]["arena"]["path"]))
    clock = cv2.imread(str(output / record["production"]["public_clock"]["path"]))
    hud = cv2.imread(str(output / record["production"]["bottom_own_hud"]["path"]))
    assert arena.shape[:2] == (843, 565)
    assert clock.size > 0
    assert hud.size > 0
    assert not list((output / "production").rglob("*raw*"))
    assert (output / "manifest.sha256").is_file()


def test_production_arena_ends_before_bottom_own_hud() -> None:
    assert (
        BOTTOM_ACTOR_ARENA_BOX.y + BOTTOM_ACTOR_ARENA_BOX.height
        <= SPECTATOR_LAYOUT_2_16.hud.y
    )


def test_inference_reference_rejects_offline_schema_and_path() -> None:
    valid = {
        "schema": PRODUCTION_ARTIFACT_SCHEMA,
        "path": "production/arena/frame.png",
        "bytes": 10,
        "sha256": "a" * 64,
        "kind": "arena",
        "inference_eligible": True,
    }
    assert validate_production_artifact_reference(valid) == valid

    offline = {
        **valid,
        "schema": OFFLINE_LABEL_ONLY_SCHEMA,
        "path": "offline_label_only/opponent_hud/frame.png",
        "inference_eligible": False,
    }
    with pytest.raises(ActorArtifactContractError, match="offline"):
        validate_production_artifact_reference(offline)


def test_live_inference_parser_rejects_offline_label_only_channel() -> None:
    from clasher.rl.live_inference_contract import (
        InferenceContractError,
        parse_public_vision_frame,
    )

    payload = {
        "schema_version": 1,
        "episode_id": "game",
        "frame_id": "frame",
        "timestamp_ms": 0,
        "offline_label_only": {
            "schema": OFFLINE_LABEL_ONLY_SCHEMA,
            "path": "offline_label_only/opponent_hud/frame.png",
        },
        "public": {},
    }
    with pytest.raises(InferenceContractError, match="unsupported keys"):
        parse_public_vision_frame(payload)


def test_private_top_counterfactual_cannot_change_any_actor_artifact(
    tmp_path: Path,
) -> None:
    original = _spectator_frame()
    changed = original.copy()
    height, width = changed.shape[:2]
    top = (0, 0, width, round(0.160 * height))
    clock = SPECTATOR_LAYOUT_2_16.clock.pixels(width, height)
    clock_pixels = changed[clock[1] : clock[3], clock[0] : clock[2]].copy()
    changed[top[1] : top[3], top[0] : top[2]] ^= np.uint8(0xFF)
    changed[clock[1] : clock[3], clock[0] : clock[2]] = clock_pixels
    first_source = tmp_path / "first"
    second_source = tmp_path / "second"
    first_source.mkdir()
    second_source.mkdir()

    first = export_bottom_actor_canary(
        canary_manifest=_canary(first_source, original),
        output_directory=tmp_path / "first_export",
    )["records"][0]
    second = export_bottom_actor_canary(
        canary_manifest=_canary(second_source, changed),
        output_directory=tmp_path / "second_export",
    )["records"][0]

    assert first["source_sha256"] != second["source_sha256"]
    assert first["offline_label_only"]["sha256"] != second["offline_label_only"]["sha256"]
    assert first["sanitized_pixel_sha256"] == second["sanitized_pixel_sha256"]
    assert first["production"] == second["production"]
    assert first["detector_input"] == second["detector_input"]
    assert first["model_pixel_inputs"] == second["model_pixel_inputs"]
    assert first["actor_tensor_export_inputs"] == second["actor_tensor_export_inputs"]


def _neutral_snapshot() -> dict[str, object]:
    return {
        "schema": NEUTRAL_SNAPSHOT_SCHEMA,
        "match_id": "match-1",
        "snapshot_id": "snapshot-1",
        "split_group_id": "youtube_replay:match-1",
        "timestamp_ms": 1200,
        "public": {
            "coordinate_frame": "absolute_world",
            "clock_seconds": 118.0,
            "entities": [
                {"track_id": "unit-1", "x_tiles": 3.25, "y_tiles": 21.5}
            ],
        },
        "players_private": {
            "0": {
                "hand": ["Knight", "Archers", "Fireball", "HogRider"],
                "hand_confidence": [0.9, 0.9, 0.9, 0.9],
                "next_card": "Skeletons",
                "next_card_confidence": 0.9,
                "elixir": 6.0,
                "elixir_confidence": 0.95,
            },
            "1": {
                "hand": ["Giant", "Bomber", "Arrows", "Musketeer"],
                "hand_confidence": [0.8, 0.8, 0.8, 0.8],
                "next_card": "Minions",
                "next_card_confidence": 0.8,
                "elixir": 4.0,
                "elixir_confidence": 0.85,
            },
        },
        "offline_evidence": {"raw_frame_sha256": "f" * 64},
    }


def test_neutral_snapshot_projects_two_private_safe_absolute_actor_views() -> None:
    snapshot = _neutral_snapshot()

    bottom = project_neutral_snapshot(snapshot, actor_id=0)
    top = project_neutral_snapshot(snapshot, actor_id=1)

    assert bottom["schema"] == ACTOR_PROJECTION_SCHEMA
    assert top["schema"] == ACTOR_PROJECTION_SCHEMA
    assert bottom["split_group_id"] == top["split_group_id"]
    assert bottom["snapshot_id"] == top["snapshot_id"]
    assert bottom["public"] == top["public"]
    assert bottom["public"]["entities"][0]["x_tiles"] == 3.25
    assert top["public"]["entities"][0]["x_tiles"] == 3.25
    assert bottom["own_private"]["next_card"] == "Skeletons"
    assert top["own_private"]["next_card"] == "Minions"
    assert "players_private" not in bottom
    assert "offline_evidence" not in top


def test_opponent_private_counterfactual_cannot_change_other_actor_projection() -> None:
    first = _neutral_snapshot()
    second = json.loads(json.dumps(first))
    second["players_private"]["1"]["hand"] = ["PEKKA"] * 4
    second["players_private"]["1"]["elixir"] = 10.0

    assert project_neutral_snapshot(first, actor_id=0) == project_neutral_snapshot(
        second, actor_id=0
    )
    assert project_neutral_snapshot(first, actor_id=1) != project_neutral_snapshot(
        second, actor_id=1
    )


def test_actor_projection_rejects_raw_or_opponent_private_fields() -> None:
    projection = project_neutral_snapshot(_neutral_snapshot(), actor_id=0)
    projection["raw_frame"] = "offline/frame.png"
    with pytest.raises(NeutralProjectionContractError, match="unsupported keys"):
        validate_actor_projection(projection)


@pytest.mark.parametrize("mutation", ["missing_next", "zero_confidence", "short_hand"])
def test_actor_projection_requires_complete_confident_hud(mutation: str) -> None:
    snapshot = _neutral_snapshot()
    own = snapshot["players_private"]["0"]
    if mutation == "missing_next":
        del own["next_card"]
    elif mutation == "zero_confidence":
        own["elixir_confidence"] = 0.0
    else:
        own["hand"] = ["Knight"] * 3

    with pytest.raises(NeutralProjectionContractError, match="incomplete_actor_hud"):
        project_neutral_snapshot(snapshot, actor_id=0)


def test_neutral_readiness_reclassifies_dual_hud_without_claiming_two_examples(
    tmp_path: Path,
) -> None:
    manifest = _canary(tmp_path, _spectator_frame())

    result = build_neutral_extraction_readiness(
        canary_manifest=manifest, output_directory=tmp_path / "neutral"
    )

    assert result["counts"]["neutral_source_frames_eligible"] == 1
    assert result["counts"]["neutral_structured_snapshots_decoded"] == 0
    assert result["counts"]["structured_actor_examples_ready"] == 0
    assert result["counts"]["potential_actor_examples_after_decode"] == 2
    assert result["counts"]["count_twice_allowed_now"] is False
    assert result["records"][0]["coordinate_frame"] == "absolute_world"
    assert result["records"][0]["source_frame"]["inference_eligible"] is False


def test_neutral_actor_id_reuses_existing_coordinate_vector_and_action_transforms() -> None:
    from clasher.rl.action_space import DiscreteTileActionSpace
    from clasher.rl.structured_obs import StructuredObservationBuilder

    builder = StructuredObservationBuilder(
        card_vocab=["Knight"],
        max_entities=8,
        canonical_perspective=True,
        canonical_lane_globals=True,
    )
    world_position = (3.25, 21.5)
    world_vector = (0.75, -0.5)
    assert builder._canonical_position(*world_position, 0) == world_position
    assert builder._canonical_vector(*world_vector, 0) == world_vector
    canonical_position = builder._canonical_position(*world_position, 1)
    canonical_vector = builder._canonical_vector(*world_vector, 1)
    assert builder._canonical_position(*canonical_position, 1) == pytest.approx(
        world_position
    )
    assert builder._canonical_vector(*canonical_vector, 1) == pytest.approx(
        world_vector
    )

    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    for actor_id in (0, 1):
        for world_x, world_y in ((0, 0), (3, 25), (8, 16), (17, 31)):
            action = action_space.encode_action(
                slot=2,
                world_x=world_x,
                world_y=world_y,
                player_id=actor_id,
            )
            decoded = action_space.decode_action(action, player_id=actor_id)
            assert decoded.slot == 2
            assert decoded.position is not None
            assert (int(decoded.position.x), int(decoded.position.y)) == (
                world_x,
                world_y,
            )
