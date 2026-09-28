"""Render fail-closed visual audits for permission-gated portrait YouTube frames.

This is an audit adapter, not a detector-training pipeline.  It deliberately
keeps sprite boxes separate from logical positions and collision hitboxes, and
it never declares a frame usable until a human review record accepts the
rendered overlay.
"""

# mypy: disable-error-code="import-untyped"
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np

from clasher.rl.perspective_sanitizer import (
    PERSPECTIVE_SURFACE_SCHEMA,
    DualHudPerspectiveSpec,
    NormalizedRegion,
    SanitizedPolicySurfaces,
    sanitize_dual_hud_frame,
)

INPUT_SCHEMA = "tv-royale-youtube-section-canary-v1"
OUTPUT_SCHEMA = "clasher.tv_royale.youtube_portrait_visual_audit.v1"
BOTTOM_ACTOR_EXPORT_SCHEMA = "clasher.live_vision.bottom_actor_crops.v1"
PRODUCTION_ARTIFACT_SCHEMA = "clasher.live_vision.production_pixel_artifact.v1"
OFFLINE_LABEL_ONLY_SCHEMA = "clasher.offline_label_only.opponent_hud.v1"
NEUTRAL_SNAPSHOT_SCHEMA = "clasher.offline.neutral_match_snapshot.v1"
NEUTRAL_SOURCE_RECORD_SCHEMA = "clasher.offline.neutral_snapshot_source_readiness.v1"
ACTOR_PROJECTION_SCHEMA = "clasher.offline.actor_projection.v1"
NEUTRAL_READINESS_SCHEMA = "clasher.tv_royale.neutral_extraction_readiness.v1"
HIGHRES_INPUT_SCHEMA = "tv-royale-youtube-explode-highres-section-v1"
HIGHRES_PROOF_SCHEMA = "clasher.tv_royale.highres_neutral_readiness_proof.v1"
PERMISSION_BASIS = "user_attested_channel_owner_approval"
GRID_COLUMNS = 18
GRID_ROWS = 32
NORMALIZED_ARENA_SIZE = (576, 896)


class RejectReason(str, Enum):
    INVALID_FRAME = "invalid_frame"
    UNSUPPORTED_ORIENTATION = "unsupported_orientation"
    EXCESSIVE_LETTERBOX = "excessive_letterbox"
    HARD_CUT = "hard_cut"
    CAPTIONS_OVER_ARENA = "captions_over_arena"
    SPECTATOR_UI_OR_MISSING_LOCAL_HUD = "spectator_ui_or_missing_local_hud"
    AMBIGUOUS_LAYOUT = "ambiguous_layout"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    MANUAL_REVIEW_REJECTED = "manual_review_rejected"


class ActorArtifactContractError(ValueError):
    """Raised when an offline-only or raw artifact approaches inference."""


class NeutralProjectionContractError(ValueError):
    """Raised when a neutral offline snapshot leaks across actor projections."""


INCOMPLETE_ACTOR_HUD = "incomplete_actor_hud"


def _validate_complete_actor_hud(payload: object) -> None:
    if not isinstance(payload, dict):
        raise NeutralProjectionContractError(f"{INCOMPLETE_ACTOR_HUD}: HUD must be an object")
    required = {
        "hand",
        "hand_confidence",
        "next_card",
        "next_card_confidence",
        "elixir",
        "elixir_confidence",
    }
    if set(payload) != required:
        raise NeutralProjectionContractError(
            f"{INCOMPLETE_ACTOR_HUD}: HUD keys must be exactly {sorted(required)}"
        )
    hand = payload["hand"]
    confidence = payload["hand_confidence"]
    if (
        not isinstance(hand, list)
        or len(hand) != 4
        or any(not isinstance(card, str) or not card.strip() for card in hand)
    ):
        raise NeutralProjectionContractError(
            f"{INCOMPLETE_ACTOR_HUD}: hand requires four nonempty card identities"
        )
    if not isinstance(confidence, list) or len(confidence) != 4:
        raise NeutralProjectionContractError(
            f"{INCOMPLETE_ACTOR_HUD}: hand requires four confidences"
        )
    numeric = [*confidence, payload["next_card_confidence"], payload["elixir_confidence"]]
    if any(
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not np.isfinite(value)
        or not 0.0 < float(value) <= 1.0
        for value in numeric
    ):
        raise NeutralProjectionContractError(
            f"{INCOMPLETE_ACTOR_HUD}: all HUD confidences must be finite in (0, 1]"
        )
    next_card = payload["next_card"]
    if not isinstance(next_card, str) or not next_card.strip():
        raise NeutralProjectionContractError(
            f"{INCOMPLETE_ACTOR_HUD}: Next card identity is required"
        )
    elixir = payload["elixir"]
    if (
        isinstance(elixir, bool)
        or not isinstance(elixir, int | float)
        or not np.isfinite(elixir)
        or not 0.0 <= float(elixir) <= 10.0
    ):
        raise NeutralProjectionContractError(
            f"{INCOMPLETE_ACTOR_HUD}: elixir must be finite in [0, 10]"
        )


@dataclass(frozen=True)
class RelativeBox:
    x: float
    y: float
    width: float
    height: float

    def pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        x1 = round(self.x * width)
        y1 = round(self.y * height)
        x2 = round((self.x + self.width) * width)
        y2 = round((self.y + self.height) * height)
        return x1, y1, x2, y2


@dataclass(frozen=True)
class PortraitLayout:
    name: str
    minimum_aspect: float
    maximum_aspect: float
    arena: RelativeBox
    clock: RelativeBox
    hud: RelativeBox


@dataclass(frozen=True)
class DetectedLayout:
    layout: PortraitLayout
    arena_pixels: tuple[int, int, int, int]
    clock_pixels: tuple[int, int, int, int]
    hud_pixels: tuple[int, int, int, int]
    hand_pixels: tuple[tuple[int, int, int, int], ...]
    next_pixels: tuple[int, int, int, int]
    elixir_number_pixels: tuple[int, int, int, int]
    elixir_bar_pixels: tuple[int, int, int, int]
    hud_purple_fraction: float
    spectator_top_hud_pixels: tuple[int, int, int, int] | None = None
    spectator_top_purple_fraction: float = 0.0


# These are source-screen candidates, not the old 428x683 Hugging Face crop.
# Coordinates are relative so both observed 886x1920 and 1182x2560 frames are
# measured in their native pixels before the arena is normalized.
PORTRAIT_LAYOUTS = (
    PortraitLayout(
        name="live_portrait_2.16",
        minimum_aspect=2.145,
        maximum_aspect=2.185,
        arena=RelativeBox(0.021, 0.073, 0.960, 0.700),
        clock=RelativeBox(0.835, 0.063, 0.165, 0.038),
        hud=RelativeBox(0.000, 0.808, 1.000, 0.155),
    ),
    PortraitLayout(
        name="live_portrait_2.22",
        minimum_aspect=2.185,
        maximum_aspect=2.245,
        arena=RelativeBox(0.020, 0.070, 0.960, 0.690),
        clock=RelativeBox(0.835, 0.058, 0.165, 0.038),
        hud=RelativeBox(0.000, 0.850, 1.000, 0.150),
    ),
    PortraitLayout(
        name="live_portrait_2.13",
        minimum_aspect=2.105,
        maximum_aspect=2.145,
        arena=RelativeBox(0.026, 0.048, 0.960, 0.710),
        clock=RelativeBox(0.845, 0.037, 0.155, 0.038),
        hud=RelativeBox(0.000, 0.845, 1.000, 0.155),
    ),
)

SPECTATOR_LAYOUT_2_16 = PortraitLayout(
    name="spectator_portrait_2.16",
    minimum_aspect=2.145,
    maximum_aspect=2.185,
    arena=RelativeBox(0.024, 0.196, 0.954, 0.685),
    clock=RelativeBox(0.790, 0.145, 0.210, 0.060),
    hud=RelativeBox(0.000, 0.855, 1.000, 0.140),
)
SPECTATOR_TOP_HUD_BOX = RelativeBox(0.000, 0.000, 1.000, 0.190)
SPECTATOR_BOTTOM_HUD_BOX = RelativeBox(0.000, 0.840, 1.000, 0.160)
SPECTATOR_TOP_ELIXIR_BAND = RelativeBox(0.000, 0.025, 0.970, 0.080)
SPECTATOR_BOTTOM_ELIXIR_BAND = RelativeBox(0.000, 0.905, 0.970, 0.080)
# Production deliberately ends the arena exactly where the retained bottom HUD
# begins.  The wider spectator crop above is audit-only and may include decor
# that overlaps the HUD; it must never be used as a production pixel surface.
BOTTOM_ACTOR_ARENA_BOX = RelativeBox(0.024, 0.196, 0.954, 0.659)
HIGHRES_PUBLIC_CLOCK_BOX = RelativeBox(0.805, 0.165, 0.195, 0.075)

# Regions within the local-player HUD crop.  They are drawn for audit rather
# than treated as trustworthy training labels.
HUD_HAND_BOXES = tuple(
    RelativeBox(x, 0.000, 0.185, 0.745) for x in (0.222, 0.410, 0.600, 0.785)
)
HUD_NEXT_BOX = RelativeBox(0.047, 0.590, 0.100, 0.365)
HUD_ELIXIR_NUMBER_BOX = RelativeBox(0.262, 0.700, 0.067, 0.160)
HUD_ELIXIR_BAR_BOX = RelativeBox(0.320, 0.700, 0.650, 0.180)

# Exact logical-grid extent in the normalized 576x896 arena.  This mirrors the
# public arena art rather than a tower or troop hitbox.
GRID_BOUNDS = (4, 82, 574, 884)
BOTTOM_ACTOR_GRID_BOUNDS = (4, 85, 574, 895)


def _clock_box_for(image: np.ndarray) -> RelativeBox:
    return HIGHRES_PUBLIC_CLOCK_BOX if image.shape[1] >= 700 else SPECTATOR_LAYOUT_2_16.clock


def _sanitizer_spec(image: np.ndarray) -> DualHudPerspectiveSpec:
    return DualHudPerspectiveSpec(
        arena=NormalizedRegion(**asdict(BOTTOM_ACTOR_ARENA_BOX)),
        clock=NormalizedRegion(**asdict(_clock_box_for(image))),
        own_hud=NormalizedRegion(**asdict(SPECTATOR_LAYOUT_2_16.hud)),
        opponent_private=NormalizedRegion(**asdict(SPECTATOR_TOP_HUD_BOX)),
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_production_artifact_reference(payload: object) -> dict[str, Any]:
    """Validate a crop reference before a detector/model/cache may consume it."""

    if not isinstance(payload, dict):
        raise ActorArtifactContractError("production artifact reference must be an object")
    allowed = {"schema", "path", "bytes", "sha256", "kind", "inference_eligible"}
    extras = sorted(set(payload) - allowed)
    if extras:
        raise ActorArtifactContractError(f"unsupported artifact keys: {extras}")
    if payload.get("schema") != PRODUCTION_ARTIFACT_SCHEMA:
        raise ActorArtifactContractError("offline or unsupported artifact schema")
    if payload.get("inference_eligible") is not True:
        raise ActorArtifactContractError("artifact is not inference eligible")
    relative_path = str(payload.get("path", ""))
    path = Path(relative_path)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] != "production"
        or "offline_label_only" in path.parts
    ):
        raise ActorArtifactContractError("artifact path is outside production crops")
    digest = str(payload.get("sha256", ""))
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ActorArtifactContractError("artifact SHA-256 is invalid")
    size = payload.get("bytes")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ActorArtifactContractError("artifact byte size must be positive")
    if payload.get("kind") not in {"arena", "public_clock", "bottom_own_hud"}:
        raise ActorArtifactContractError("artifact kind is not an actor input crop")
    return payload


def project_neutral_snapshot(
    snapshot: object, *, actor_id: int
) -> dict[str, Any]:
    """Materialize one actor view without flipping absolute world coordinates."""

    if not isinstance(snapshot, dict) or snapshot.get("schema") != NEUTRAL_SNAPSHOT_SCHEMA:
        raise NeutralProjectionContractError("unsupported neutral snapshot schema")
    if actor_id not in (0, 1):
        raise NeutralProjectionContractError("actor_id must be 0 or 1")
    allowed = {
        "schema",
        "match_id",
        "snapshot_id",
        "split_group_id",
        "timestamp_ms",
        "public",
        "players_private",
        "offline_evidence",
    }
    extras = sorted(set(snapshot) - allowed)
    if extras:
        raise NeutralProjectionContractError(f"neutral snapshot has unsupported keys: {extras}")
    public = snapshot.get("public")
    players = snapshot.get("players_private")
    if not isinstance(public, dict) or public.get("coordinate_frame") != "absolute_world":
        raise NeutralProjectionContractError("public state must use absolute_world coordinates")
    if not isinstance(players, dict) or set(players) != {"0", "1"}:
        raise NeutralProjectionContractError("neutral snapshot requires both private player states")
    own = players.get(str(actor_id))
    if not isinstance(own, dict):
        raise NeutralProjectionContractError("actor private state must be an object")
    _validate_complete_actor_hud(own)
    # JSON round trips create detached structures and make accidental references
    # back into the privileged neutral record impossible.
    detached_public = json.loads(json.dumps(public))
    detached_own = json.loads(json.dumps(own))
    projection = {
        "schema": ACTOR_PROJECTION_SCHEMA,
        "match_id": str(snapshot.get("match_id", "")),
        "snapshot_id": str(snapshot.get("snapshot_id", "")),
        "split_group_id": str(snapshot.get("split_group_id", "")),
        "timestamp_ms": int(snapshot.get("timestamp_ms", 0)),
        "actor_id": actor_id,
        "public": detached_public,
        "own_private": detached_own,
    }
    validate_actor_projection(projection)
    return projection


def validate_actor_projection(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema") != ACTOR_PROJECTION_SCHEMA:
        raise NeutralProjectionContractError("unsupported actor projection schema")
    allowed = {
        "schema",
        "match_id",
        "snapshot_id",
        "split_group_id",
        "timestamp_ms",
        "actor_id",
        "public",
        "own_private",
    }
    extras = sorted(set(payload) - allowed)
    if extras:
        raise NeutralProjectionContractError(
            f"actor projection has unsupported keys: {extras}"
        )
    serialized = json.dumps(payload, sort_keys=True).lower()
    forbidden = (
        "players_private",
        "offline_evidence",
        "opponent_hand",
        "opponent_elixir",
        "opponent_next_card",
        "raw_frame",
        "hud_path",
    )
    if any(name in serialized for name in forbidden):
        raise NeutralProjectionContractError("actor projection contains privileged fields")
    public = payload.get("public")
    if not isinstance(public, dict) or public.get("coordinate_frame") != "absolute_world":
        raise NeutralProjectionContractError("actor public coordinates are not absolute_world")
    if payload.get("actor_id") not in (0, 1):
        raise NeutralProjectionContractError("actor_id must be 0 or 1")
    _validate_complete_actor_hud(payload.get("own_private"))
    return payload


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _absolute_child(parent: tuple[int, int, int, int], child: RelativeBox) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = parent
    cx1, cy1, cx2, cy2 = child.pixels(x2 - x1, y2 - y1)
    return x1 + cx1, y1 + cy1, x1 + cx2, y1 + cy2


def _crop_box(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = box
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        raise ValueError(f"empty crop {box} for image {image.shape}")
    return cast(np.ndarray, np.asarray(crop).copy())


def _write_image(path: Path, image: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image, [cv2.IMWRITE_PNG_COMPRESSION, 3]):
        raise RuntimeError(f"could not write {path}")
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def _purple_fraction(image: np.ndarray, box: tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = box
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return 0.0
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.asarray((125, 45, 35)), np.asarray((179, 255, 255)))
    return float(np.count_nonzero(mask) / mask.size)


def _letterbox_fraction(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    band = max(2, round(min(gray.shape) * 0.015))
    borders = np.concatenate(
        (
            gray[:band].reshape(-1),
            gray[-band:].reshape(-1),
            gray[:, :band].reshape(-1),
            gray[:, -band:].reshape(-1),
        )
    )
    return float(np.count_nonzero(borders < 8) / borders.size)


def _hard_cut_score(previous: np.ndarray, current: np.ndarray) -> float:
    if previous.shape != current.shape:
        return 1.0
    previous_small = cv2.resize(previous, (96, 160), interpolation=cv2.INTER_AREA)
    current_small = cv2.resize(current, (96, 160), interpolation=cv2.INTER_AREA)
    return float(np.mean(cv2.absdiff(previous_small, current_small)) / 255.0)


def detect_layout(image: np.ndarray) -> tuple[DetectedLayout | None, RejectReason | None, dict[str, float]]:
    if image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 240:
        return None, RejectReason.INVALID_FRAME, {}
    height, width = image.shape[:2]
    if height <= width:
        return None, RejectReason.UNSUPPORTED_ORIENTATION, {"aspect": height / width}
    aspect = height / width
    letterbox = _letterbox_fraction(image)
    if letterbox >= 0.78:
        return None, RejectReason.EXCESSIVE_LETTERBOX, {
            "aspect": aspect,
            "letterbox_fraction": letterbox,
        }
    candidates = [
        layout
        for layout in PORTRAIT_LAYOUTS
        if layout.minimum_aspect <= aspect < layout.maximum_aspect
    ]
    if len(candidates) != 1:
        return None, RejectReason.AMBIGUOUS_LAYOUT, {
            "aspect": aspect,
            "letterbox_fraction": letterbox,
            "candidate_count": float(len(candidates)),
        }
    top_purple = _purple_fraction(
        image, SPECTATOR_TOP_ELIXIR_BAND.pixels(width, height)
    )
    bottom_purple = _purple_fraction(
        image, SPECTATOR_BOTTOM_ELIXIR_BAND.pixels(width, height)
    )
    spectator = top_purple >= 0.008 and bottom_purple >= 0.008
    layout = SPECTATOR_LAYOUT_2_16 if spectator else candidates[0]
    if spectator and width >= 700:
        layout = replace(layout, clock=HIGHRES_PUBLIC_CLOCK_BOX)
    arena = layout.arena.pixels(width, height)
    clock = layout.clock.pixels(width, height)
    hud = layout.hud.pixels(width, height)
    hand = tuple(_absolute_child(hud, child) for child in HUD_HAND_BOXES)
    next_box = _absolute_child(hud, HUD_NEXT_BOX)
    elixir_number = _absolute_child(hud, HUD_ELIXIR_NUMBER_BOX)
    elixir_bar = _absolute_child(hud, HUD_ELIXIR_BAR_BOX)
    purple = _purple_fraction(image, elixir_bar)
    metrics = {
        "aspect": aspect,
        "letterbox_fraction": letterbox,
        "hud_purple_fraction": purple,
        "spectator_top_purple_fraction": top_purple,
        "spectator_bottom_purple_fraction": bottom_purple,
    }
    # A local-player view must expose its own elixir/hand HUD.  This rejects
    # spectator/replay framing rather than silently manufacturing private HUD
    # observations from an arena-only view.
    if spectator:
        return (
            DetectedLayout(
                layout=layout,
                arena_pixels=arena,
                clock_pixels=clock,
                hud_pixels=hud,
                hand_pixels=(),
                next_pixels=(0, 0, 0, 0),
                elixir_number_pixels=(0, 0, 0, 0),
                elixir_bar_pixels=(0, 0, 0, 0),
                hud_purple_fraction=bottom_purple,
                spectator_top_hud_pixels=SPECTATOR_TOP_HUD_BOX.pixels(
                    width, height
                ),
                spectator_top_purple_fraction=top_purple,
            ),
            RejectReason.SPECTATOR_UI_OR_MISSING_LOCAL_HUD,
            metrics,
        )
    if purple < 0.01:
        return None, RejectReason.SPECTATOR_UI_OR_MISSING_LOCAL_HUD, metrics
    return (
        DetectedLayout(
            layout=layout,
            arena_pixels=arena,
            clock_pixels=clock,
            hud_pixels=hud,
            hand_pixels=hand,
            next_pixels=next_box,
            elixir_number_pixels=elixir_number,
            elixir_bar_pixels=elixir_bar,
            hud_purple_fraction=purple,
        ),
        None,
        metrics,
    )


def detect_bottom_actor_layout(
    image: np.ndarray,
) -> tuple[
    SanitizedPolicySurfaces | None,
    RejectReason | None,
    dict[str, float],
]:
    """Classify production geometry without consulting opponent-private pixels."""

    if image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 240:
        return None, RejectReason.INVALID_FRAME, {}
    height, width = image.shape[:2]
    if height <= width:
        return None, RejectReason.UNSUPPORTED_ORIENTATION, {
            "aspect": height / width
        }
    aspect = height / width
    if not (
        SPECTATOR_LAYOUT_2_16.minimum_aspect
        <= aspect
        < SPECTATOR_LAYOUT_2_16.maximum_aspect
    ):
        return None, RejectReason.AMBIGUOUS_LAYOUT, {
            "aspect": aspect,
        }
    # This is the first pixel-bearing operation.  Every later production check
    # consumes only allowlisted surfaces, so opponent-private pixels cannot
    # influence acceptance, cut detection, caches, or actor artifacts.
    surfaces = sanitize_dual_hud_frame(image, _sanitizer_spec(image))
    safe_letterbox = _letterbox_fraction(surfaces.arena)
    if safe_letterbox >= 0.78:
        return None, RejectReason.EXCESSIVE_LETTERBOX, {
            "aspect": aspect,
            "safe_arena_letterbox_fraction": safe_letterbox,
        }
    bottom_purple = _purple_fraction(
        surfaces.own_hud,
        (0, 0, surfaces.own_hud.shape[1], surfaces.own_hud.shape[0]),
    )
    metrics = {
        "aspect": aspect,
        "safe_arena_letterbox_fraction": safe_letterbox,
        "bottom_own_hud_purple_fraction": bottom_purple,
    }
    if bottom_purple < 0.008:
        return (
            None,
            RejectReason.SPECTATOR_UI_OR_MISSING_LOCAL_HUD,
            metrics,
        )
    return surfaces, None, metrics


def _draw_box(image: np.ndarray, box: tuple[int, int, int, int], color: tuple[int, int, int], label: str) -> None:
    x1, y1, x2, y2 = box
    cv2.rectangle(image, (x1, y1), (x2, y2), color, max(1, image.shape[1] // 500))
    cv2.putText(
        image,
        label,
        (x1 + 3, max(18, y1 - 5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        max(0.4, image.shape[1] / 1600),
        color,
        max(1, image.shape[1] // 700),
        cv2.LINE_AA,
    )


def _arena_point_to_source(
    arena: tuple[int, int, int, int], point: tuple[float, float]
) -> tuple[int, int]:
    x1, y1, x2, y2 = arena
    return round(x1 + point[0] * (x2 - x1)), round(y1 + point[1] * (y2 - y1))


def _draw_grid(
    normalized: np.ndarray,
    bounds: tuple[int, int, int, int] = GRID_BOUNDS,
) -> None:
    x1, y1, x2, y2 = bounds
    for column in range(GRID_COLUMNS + 1):
        x = round(x1 + column * (x2 - x1) / GRID_COLUMNS)
        cv2.line(normalized, (x, y1), (x, y2), (170, 170, 170), 1)
    for row in range(GRID_ROWS + 1):
        y = round(y1 + row * (y2 - y1) / GRID_ROWS)
        color = (0, 255, 255) if row == GRID_ROWS // 2 else (170, 170, 170)
        cv2.line(normalized, (x1, y), (x2, y), color, 2 if row == GRID_ROWS // 2 else 1)


def render_audit(
    image: np.ndarray,
    detected: DetectedLayout,
    overlays: dict[str, Any] | None = None,
) -> np.ndarray:
    overlays = overlays or {}
    full = image.copy()
    _draw_box(full, detected.arena_pixels, (0, 255, 255), "ARENA CROP")
    _draw_box(full, detected.clock_pixels, (255, 230, 40), "PUBLIC CLOCK")
    if detected.spectator_top_hud_pixels is not None:
        _draw_box(
            full,
            detected.spectator_top_hud_pixels,
            (20, 20, 255),
            "REJECT: PRIVATE SPECTATOR TOP HUD",
        )
        _draw_box(
            full,
            SPECTATOR_BOTTOM_HUD_BOX.pixels(full.shape[1], full.shape[0]),
            (20, 20, 255),
            "REJECT: PRIVATE SPECTATOR BOTTOM HUD",
        )
    else:
        for index, box in enumerate(detected.hand_pixels, start=1):
            _draw_box(full, box, (60, 220, 60), f"OWN HAND {index}")
        _draw_box(full, detected.next_pixels, (255, 180, 60), "NEXT")
        _draw_box(full, detected.elixir_number_pixels, (230, 80, 230), "ELIXIR #")
        _draw_box(full, detected.elixir_bar_pixels, (230, 80, 230), "ELIXIR BAR")

    ax1, ay1, ax2, ay2 = detected.arena_pixels
    arena = image[ay1:ay2, ax1:ax2]
    normalized = cv2.resize(arena, NORMALIZED_ARENA_SIZE, interpolation=cv2.INTER_AREA)
    _draw_grid(normalized)

    for item in overlays.get("sprite_boxes", []):
        box = item["box"]
        sx1, sy1 = _arena_point_to_source(detected.arena_pixels, (float(box[0]), float(box[1])))
        sx2, sy2 = _arena_point_to_source(detected.arena_pixels, (float(box[2]), float(box[3])))
        _draw_box(full, (sx1, sy1, sx2, sy2), (255, 120, 30), f"SPRITE: {item.get('label', '?')}")
        center = _arena_point_to_source(
            detected.arena_pixels,
            ((float(box[0]) + float(box[2])) / 2, (float(box[1]) + float(box[3])) / 2),
        )
        cv2.drawMarker(full, center, (255, 120, 30), cv2.MARKER_CROSS, 18, 2)
    for item in overlays.get("deployment_points", []):
        point = _arena_point_to_source(
            detected.arena_pixels, (float(item["x"]), float(item["y"]))
        )
        cv2.drawMarker(full, point, (40, 255, 40), cv2.MARKER_TILTED_CROSS, 24, 3)
        cv2.putText(full, f"DEPLOY {item.get('card', '?')}", (point[0] + 8, point[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 255, 40), 2, cv2.LINE_AA)
    for item in overlays.get("events", []):
        point = _arena_point_to_source(
            detected.arena_pixels, (float(item["x"]), float(item["y"]))
        )
        cv2.drawMarker(full, point, (40, 200, 255), cv2.MARKER_DIAMOND, 22, 2)
        cv2.putText(full, f"EVENT {item.get('label', '?')}", (point[0] + 8, point[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 200, 255), 2, cv2.LINE_AA)
    for item in overlays.get("statuses", []):
        point = _arena_point_to_source(
            detected.arena_pixels, (float(item["x"]), float(item["y"]))
        )
        cv2.circle(full, point, 18, (255, 80, 255), 2)
        cv2.putText(full, f"STATUS {item.get('label', '?')}", (point[0] + 8, point[1] + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 80, 255), 2, cv2.LINE_AA)

    banner_height = max(48, round(full.shape[0] * 0.035))
    cv2.rectangle(full, (0, 0), (full.shape[1], banner_height), (0, 0, 0), -1)
    cv2.putText(full, "BOXES = VISIBLE SPRITES/REGIONS, NEVER SIMULATOR HITBOXES", (12, round(banner_height * 0.68)), cv2.FONT_HERSHEY_SIMPLEX, max(0.45, full.shape[1] / 1450), (255, 255, 255), max(1, full.shape[1] // 700), cv2.LINE_AA)

    target_height = full.shape[0]
    normalized_width = round(normalized.shape[1] * target_height / normalized.shape[0])
    normalized_panel = cv2.resize(normalized, (normalized_width, target_height), interpolation=cv2.INTER_AREA)
    return np.concatenate((full, normalized_panel), axis=1)


def render_bottom_actor_preview(
    *, arena: np.ndarray, public_clock: np.ndarray, bottom_hud: np.ndarray
) -> np.ndarray:
    normalized = cv2.resize(arena, NORMALIZED_ARENA_SIZE, interpolation=cv2.INTER_AREA)
    _draw_grid(normalized, BOTTOM_ACTOR_GRID_BOUNDS)
    hud_height = max(120, round(bottom_hud.shape[0] * normalized.shape[1] / bottom_hud.shape[1]))
    hud = cv2.resize(bottom_hud, (normalized.shape[1], hud_height), interpolation=cv2.INTER_AREA)
    for index, relative in enumerate(HUD_HAND_BOXES, start=1):
        _draw_box(hud, relative.pixels(hud.shape[1], hud.shape[0]), (60, 220, 60), f"OWN {index}")
    _draw_box(hud, HUD_NEXT_BOX.pixels(hud.shape[1], hud.shape[0]), (255, 180, 60), "NEXT")
    _draw_box(hud, HUD_ELIXIR_NUMBER_BOX.pixels(hud.shape[1], hud.shape[0]), (230, 80, 230), "ELIXIR #")
    _draw_box(hud, HUD_ELIXIR_BAR_BOX.pixels(hud.shape[1], hud.shape[0]), (230, 80, 230), "ELIXIR BAR")
    footer = np.zeros((84, normalized.shape[1], 3), dtype=np.uint8)
    clock_width = min(150, round(public_clock.shape[1] * 70 / public_clock.shape[0]))
    clock = cv2.resize(public_clock, (clock_width, 70), interpolation=cv2.INTER_AREA)
    footer[7:77, 7 : 7 + clock_width] = clock
    cv2.putText(footer, "PUBLIC CLOCK", (14 + clock_width, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 230, 40), 2, cv2.LINE_AA)
    cv2.putText(footer, "TOP OPPONENT HUD ABSENT", (14 + clock_width, 61), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (60, 220, 60), 2, cv2.LINE_AA)
    return np.concatenate((normalized, hud, footer), axis=0)


def _production_reference(
    artifact: dict[str, Any], *, output_directory: Path, kind: str
) -> dict[str, Any]:
    path = Path(str(artifact["path"]))
    reference = {
        "schema": PRODUCTION_ARTIFACT_SCHEMA,
        "path": str(path.relative_to(output_directory)),
        "bytes": artifact["bytes"],
        "sha256": artifact["sha256"],
        "kind": kind,
        "inference_eligible": True,
    }
    validate_production_artifact_reference(reference)
    return reference


def export_bottom_actor_canary(
    *, canary_manifest: Path, output_directory: Path
) -> dict[str, Any]:
    """Export only disjoint production crops for the bottom-player perspective."""

    source = json.loads(canary_manifest.read_text(encoding="utf-8"))
    if source.get("schema") != INPUT_SCHEMA:
        raise ValueError(f"input schema must be {INPUT_SCHEMA}")
    permission = source.get("permission_provenance", {})
    if permission.get("basis") != PERMISSION_BASIS:
        raise ValueError(f"permission basis must be {PERMISSION_BASIS}")
    if permission.get("public_cc_license_claimed") is not False:
        raise ValueError("permission must explicitly state public_cc_license_claimed=false")
    if output_directory.exists():
        raise FileExistsError(f"output already exists: {output_directory}")
    output_directory.mkdir(parents=True)

    records: list[dict[str, Any]] = []
    accepted = 0
    reasons: dict[str, int] = {}
    previous_by_section: dict[tuple[str, str], SanitizedPolicySurfaces] = {}
    for row in _frame_rows(source, canary_manifest.parent):
        path = row["path"]
        source_sha = file_sha256(path)
        if source_sha != row["declared_sha256"]:
            raise ValueError(f"frame hash mismatch: {path}")
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"could not decode frame: {path}")
        key = f"{row['video_id']}/{row['section']}/{path.name}"
        surfaces, reason, metrics = detect_bottom_actor_layout(image)
        layout_supported = surfaces is not None
        sequence_key = (row["video_id"], row["section"])
        previous = previous_by_section.get(sequence_key)
        if previous is not None and surfaces is not None:
            metrics["hard_cut_score"] = _hard_cut_score(
                previous.arena, surfaces.arena
            )
            if metrics["hard_cut_score"] >= 0.46:
                layout_supported = False
                reason = RejectReason.HARD_CUT
        if surfaces is not None:
            previous_by_section[sequence_key] = surfaces
        if not layout_supported or surfaces is None:
            rejected = reason or RejectReason.AMBIGUOUS_LAYOUT
            reasons[rejected.value] = reasons.get(rejected.value, 0) + 1
            records.append(
                {
                    "key": key,
                    "source_sha256": source_sha,
                    "accepted": False,
                    "reject_reason": rejected.value,
                    "metrics": metrics,
                }
            )
            continue

        stem = f"{row['video_id']}_{row['section']}_{path.stem}"
        sanitizer_spec = _sanitizer_spec(image)
        actor_arena_pixels = sanitizer_spec.arena.pixels(
            image.shape[1], image.shape[0]
        )
        arena = surfaces.arena
        clock = surfaces.clock
        own_hud = surfaces.own_hud
        opponent_hud_pixels = sanitizer_spec.opponent_private.pixels(
            image.shape[1], image.shape[0]
        )
        opponent_hud = _crop_box(image, opponent_hud_pixels)
        source_pixels = image.shape[0] * image.shape[1]
        retained_source_pixels = sum(
            (box[2] - box[0]) * (box[3] - box[1])
            for box in (
                actor_arena_pixels,
                sanitizer_spec.clock.pixels(image.shape[1], image.shape[0]),
                sanitizer_spec.own_hud.pixels(image.shape[1], image.shape[0]),
            )
        )
        retained_fraction = retained_source_pixels / source_pixels

        arena_artifact = _write_image(output_directory / "production" / "arena" / f"{stem}.png", arena)
        clock_artifact = _write_image(output_directory / "production" / "public_clock" / f"{stem}.png", clock)
        hud_artifact = _write_image(output_directory / "production" / "bottom_own_hud" / f"{stem}.png", own_hud)
        offline_artifact = _write_image(output_directory / "offline_label_only" / "opponent_hud" / f"{stem}.png", opponent_hud)
        preview = render_bottom_actor_preview(
            arena=arena, public_clock=clock, bottom_hud=own_hud
        )
        preview_artifact = _write_image(output_directory / "manual_audit" / f"{stem}.png", preview)

        production = {
            "arena": _production_reference(arena_artifact, output_directory=output_directory, kind="arena"),
            "public_clock": _production_reference(clock_artifact, output_directory=output_directory, kind="public_clock"),
            "bottom_own_hud": _production_reference(hud_artifact, output_directory=output_directory, kind="bottom_own_hud"),
        }
        accepted += 1
        records.append(
            {
                "key": key,
                "source_sha256": source_sha,
                "accepted": True,
                "reject_reason": None,
                "layout": asdict(SPECTATOR_LAYOUT_2_16),
                "source_dimensions": [image.shape[1], image.shape[0]],
                "source_relative_regions": {
                    "arena": asdict(BOTTOM_ACTOR_ARENA_BOX),
                    "public_clock": asdict(_clock_box_for(image)),
                    "bottom_own_hud": asdict(SPECTATOR_LAYOUT_2_16.hud),
                    "top_opponent_hud": asdict(SPECTATOR_TOP_HUD_BOX),
                },
                "production": production,
                "sanitized_surface_schema": PERSPECTIVE_SURFACE_SCHEMA,
                "sanitized_pixel_sha256": surfaces.pixel_sha256,
                "detector_input": production["arena"],
                "model_pixel_inputs": list(production.values()),
                "actor_tensor_export_inputs": list(production.values()),
                "offline_label_only": {
                    "schema": OFFLINE_LABEL_ONLY_SCHEMA,
                    "path": str(Path(str(offline_artifact["path"])).relative_to(output_directory)),
                    "bytes": offline_artifact["bytes"],
                    "sha256": offline_artifact["sha256"],
                    "inference_eligible": False,
                },
                "manual_audit": {
                    "path": str(Path(str(preview_artifact["path"])).relative_to(output_directory)),
                    "bytes": preview_artifact["bytes"],
                    "sha256": preview_artifact["sha256"],
                },
                "information_loss": {
                    "top_opponent_hud_removed": True,
                    "opponent_hand_next_elixir_removed": True,
                    "public_clock_retained_separately": True,
                    "bottom_own_hand_next_elixir_retained": True,
                    "arena_retained_at_native_crop_resolution": True,
                    "full_raw_frame_exported_to_production": False,
                    "source_pixel_fraction_retained": retained_fraction,
                    "source_pixel_fraction_discarded": 1.0 - retained_fraction,
                    "arena_source_dimensions": [
                        actor_arena_pixels[2] - actor_arena_pixels[0],
                        actor_arena_pixels[3] - actor_arena_pixels[1],
                    ],
                    "arena_output_dimensions": [arena.shape[1], arena.shape[0]],
                    "arena_pixels_resampled": False,
                    "manual_preview_normalized_dimensions": list(
                        NORMALIZED_ARENA_SIZE
                    ),
                },
                "metrics": metrics,
            }
        )

    payload = {
        "schema": BOTTOM_ACTOR_EXPORT_SCHEMA,
        "source_manifest": str(canary_manifest),
        "source_manifest_sha256": file_sha256(canary_manifest),
        "permission_provenance": {
            "basis": PERMISSION_BASIS,
            "public_cc_license_claimed": False,
        },
        "perspective": "bottom_player",
        "production_contract": {
            "raw_full_frame_cached": False,
            "detector_input_kinds": ["arena"],
            "model_input_kinds": ["arena", "public_clock", "bottom_own_hud"],
            "top_opponent_hud_schema": OFFLINE_LABEL_ONLY_SCHEMA,
            "top_opponent_hud_inference_eligible": False,
        },
        "accepted": accepted,
        "rejected": len(records) - accepted,
        "reject_reasons": reasons,
        "records": records,
    }
    manifest_path = output_directory / "manifest.json"
    _atomic_write_json(manifest_path, payload)
    digest = file_sha256(manifest_path)
    (output_directory / "manifest.sha256").write_text(
        f"{digest}  manifest.json\n", encoding="ascii"
    )
    return payload


def build_neutral_extraction_readiness(
    *, canary_manifest: Path, output_directory: Path
) -> dict[str, Any]:
    """Reclassify dual-HUD footage for one neutral offline match-state record."""

    source = json.loads(canary_manifest.read_text(encoding="utf-8"))
    if source.get("schema") != INPUT_SCHEMA:
        raise ValueError(f"input schema must be {INPUT_SCHEMA}")
    permission = source.get("permission_provenance", {})
    if permission.get("basis") != PERMISSION_BASIS:
        raise ValueError(f"permission basis must be {PERMISSION_BASIS}")
    if permission.get("public_cc_license_claimed") is not False:
        raise ValueError("permission must explicitly state public_cc_license_claimed=false")
    output_directory.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    source_ready = 0
    reasons: dict[str, int] = {}
    match_ids: set[str] = set()
    for row in _frame_rows(source, canary_manifest.parent):
        path = row["path"]
        source_sha = file_sha256(path)
        if source_sha != row["declared_sha256"]:
            raise ValueError(f"frame hash mismatch: {path}")
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"could not decode frame: {path}")
        detected, reason, metrics = detect_layout(image)
        dual_hud = (
            detected is not None
            and detected.spectator_top_hud_pixels is not None
            and reason == RejectReason.SPECTATOR_UI_OR_MISSING_LOCAL_HUD
        )
        if not dual_hud:
            reject = reason or RejectReason.AMBIGUOUS_LAYOUT
            reasons[reject.value] = reasons.get(reject.value, 0) + 1
        else:
            source_ready += 1
        video_id = str(row["video_id"])
        snapshot_id = hashlib.sha256(
            f"{video_id}\0{row['section']}\0{path.name}\0{source_sha}".encode()
        ).hexdigest()
        split_group_id = f"youtube_replay:{video_id}"
        match_ids.add(video_id)
        records.append(
            {
                "schema": NEUTRAL_SOURCE_RECORD_SCHEMA,
                "match_id": video_id,
                "snapshot_id": snapshot_id,
                "split_group_id": split_group_id,
                "source_frame": {
                    "schema": "clasher.offline_extractor.raw_spectator_frame.v1",
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": source_sha,
                    "offline_extractor_only": True,
                    "inference_eligible": False,
                },
                "neutral_source_eligible": dual_hud,
                "reject_reason": None if dual_hud else (reason or RejectReason.AMBIGUOUS_LAYOUT).value,
                "coordinate_frame": "absolute_world",
                "source_dimensions": [image.shape[1], image.shape[0]],
                "source_relative_regions": {
                    "arena": asdict(BOTTOM_ACTOR_ARENA_BOX),
                    "public_clock": asdict(_clock_box_for(image)),
                    "top_player_hud": asdict(SPECTATOR_TOP_HUD_BOX),
                    "bottom_player_hud": asdict(SPECTATOR_LAYOUT_2_16.hud),
                },
                "field_readiness": {
                    "arena_and_towers": "visually_present_not_decoded",
                    "entities_absolute_positions": "requires_detector_validation",
                    "hp_bars": "requires_bar_association_validation",
                    "statuses_effects_projectiles": "requires_detector_and_onset_labels",
                    "public_clock": "visually_present_not_ocr_validated",
                    "top_hand_next_elixir": "visually_complete_not_decoded",
                    "bottom_hand_next_elixir": "visually_complete_not_decoded",
                    "play_and_deployment_events": "two_second_frame_interval_insufficient_for_100ms_gate",
                },
                "actor_projection_readiness": {
                    "potential_actor_ids": [0, 1],
                    "structured_actor_examples_ready": 0,
                    "reason": "neutral structured fields are not decoded yet",
                    "count_twice_allowed": False,
                },
                "metrics": metrics,
            }
        )

    payload = {
        "schema": NEUTRAL_READINESS_SCHEMA,
        "source_manifest": str(canary_manifest),
        "source_manifest_sha256": file_sha256(canary_manifest),
        "permission_provenance": {
            "basis": PERMISSION_BASIS,
            "public_cc_license_claimed": False,
        },
        "reclassification": {
            "prior_live_full_frame_result": "typed_reject_dual_hud_private_leakage",
            "neutral_offline_extractor_result": "eligible_source_when_dual_hud_and_arena_are_visible",
            "raw_frame_inference_eligible": False,
        },
        "counts": {
            "unique_replays": len(match_ids),
            "source_frames": len(records),
            "neutral_source_frames_eligible": source_ready,
            "neutral_source_frames_rejected": len(records) - source_ready,
            "neutral_structured_snapshots_decoded": 0,
            "structured_actor_examples_ready": 0,
            "potential_actor_examples_after_decode": source_ready * 2,
            "count_twice_allowed_now": False,
        },
        "reject_reasons": reasons,
        "split_contract": {
            "group_key": "split_group_id",
            "all_snapshots_and_both_actor_projections_from_one_replay_stay_together": True,
        },
        "actor_projection_contract": {
            "neutral_record_coordinates": "absolute_world",
            "image_flip_or_rotation": False,
            "observation_canonicalization": "StructuredObservationBuilder(canonical_perspective=True, canonical_lane_globals=True)",
            "action_canonicalization": "DiscreteTileActionSpace(canonical_perspective=True) encode_action/decode_action",
            "perspective_selector": "actor_id",
        },
        "records": records,
    }
    manifest_path = output_directory / "manifest.json"
    _atomic_write_json(manifest_path, payload)
    digest = file_sha256(manifest_path)
    (output_directory / "manifest.sha256").write_text(
        f"{digest}  manifest.json\n", encoding="ascii"
    )
    return payload


def build_highres_neutral_readiness_proof(
    *,
    highres_manifest: Path,
    permission_manifest: Path,
    output_directory: Path,
) -> dict[str, Any]:
    """Audit the bounded high-resolution proof against authoritative permission."""

    source = json.loads(highres_manifest.read_text(encoding="utf-8"))
    if source.get("schema") != HIGHRES_INPUT_SCHEMA:
        raise ValueError(f"high-resolution schema must be {HIGHRES_INPUT_SCHEMA}")
    metadata = json.loads(permission_manifest.read_text(encoding="utf-8"))
    permission = metadata.get("permission_provenance", {})
    if permission.get("basis") != PERMISSION_BASIS:
        raise ValueError(f"permission basis must be {PERMISSION_BASIS}")
    if permission.get("public_cc_license_claimed") is not False:
        raise ValueError("permission must explicitly state public_cc_license_claimed=false")
    source_info = source.get("source", {})
    video_id = str(source_info.get("id", ""))
    authorized_ids = {str(row.get("id", "")) for row in metadata.get("videos", [])}
    if (
        source_info.get("availability") != "public"
        or source_info.get("access_class") != "public"
        or video_id not in authorized_ids
    ):
        raise ValueError("high-resolution source is not an authorized public video")

    output_directory.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    ready = 0
    for frame in source.get("frames", []):
        path = highres_manifest.parent / str(frame["path"])
        digest = file_sha256(path)
        if digest != frame.get("sha256"):
            raise ValueError(f"frame hash mismatch: {path}")
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"could not decode frame: {path}")
        detected, reason, metrics = detect_layout(image)
        eligible = (
            detected is not None
            and detected.spectator_top_hud_pixels is not None
            and reason == RejectReason.SPECTATOR_UI_OR_MISSING_LOCAL_HUD
        )
        if eligible:
            ready += 1
        arena_box = BOTTOM_ACTOR_ARENA_BOX.pixels(image.shape[1], image.shape[0])
        arena_dimensions = [arena_box[2] - arena_box[0], arena_box[3] - arena_box[1]]
        records.append(
            {
                "source_frame": {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": digest,
                    "offline_extractor_only": True,
                    "inference_eligible": False,
                },
                "neutral_source_eligible": eligible,
                "reject_reason": None if eligible else (reason or RejectReason.AMBIGUOUS_LAYOUT).value,
                "source_dimensions": [image.shape[1], image.shape[0]],
                "arena_native_dimensions": arena_dimensions,
                "linear_ratio_vs_hf_428x683": [
                    arena_dimensions[0] / 428.0,
                    arena_dimensions[1] / 683.0,
                ],
                "source_relative_regions": {
                    "arena": asdict(BOTTOM_ACTOR_ARENA_BOX),
                    "public_clock": asdict(_clock_box_for(image)),
                    "top_player_hud": asdict(SPECTATOR_TOP_HUD_BOX),
                    "bottom_player_hud": asdict(SPECTATOR_LAYOUT_2_16.hud),
                },
                "metrics": metrics,
            }
        )

    minimum_ratio = min(
        min(record["linear_ratio_vs_hf_428x683"]) for record in records
    )
    payload = {
        "schema": HIGHRES_PROOF_SCHEMA,
        "source_manifest": str(highres_manifest),
        "source_manifest_sha256": file_sha256(highres_manifest),
        "permission_manifest": str(permission_manifest),
        "permission_manifest_sha256": file_sha256(permission_manifest),
        "permission_provenance": {
            "basis": PERMISSION_BASIS,
            "public_cc_license_claimed": False,
        },
        "counts": {
            "frames": len(records),
            "neutral_source_frames_eligible": ready,
            "neutral_source_frames_rejected": len(records) - ready,
        },
        "resolution_gate": {
            "hf_arena_dimensions": [428, 683],
            "minimum_linear_ratio": minimum_ratio,
            "at_least_2x_both_axes": minimum_ratio >= 2.0,
            "scope": "one video and one section only; not the ten-video replacement gate",
        },
        "structured_snapshots_decoded": 0,
        "actor_examples_ready": 0,
        "records": records,
    }
    manifest_path = output_directory / "manifest.json"
    _atomic_write_json(manifest_path, payload)
    digest = file_sha256(manifest_path)
    (output_directory / "manifest.sha256").write_text(
        f"{digest}  manifest.json\n", encoding="ascii"
    )
    return payload


def _load_json_object(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _frame_rows(manifest: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for video in manifest.get("videos", []):
        for section in video.get("sections", []):
            for frame in section.get("frames", []):
                rows.append(
                    {
                        "video_id": video["id"],
                        "section": section["label"],
                        "path": root / frame["path"],
                        "declared_sha256": frame["sha256"],
                    }
                )
    return rows


def audit_canary(
    *,
    canary_manifest: Path,
    output_directory: Path,
    overlays_path: Path | None = None,
    reviews_path: Path | None = None,
) -> dict[str, Any]:
    source = json.loads(canary_manifest.read_text(encoding="utf-8"))
    if source.get("schema") != INPUT_SCHEMA:
        raise ValueError(f"input schema must be {INPUT_SCHEMA}")
    permission = source.get("permission_provenance", {})
    if permission.get("basis") != PERMISSION_BASIS:
        raise ValueError(f"permission basis must be {PERMISSION_BASIS}")
    if permission.get("public_cc_license_claimed") is not False:
        raise ValueError("permission must explicitly state public_cc_license_claimed=false")

    overlays = _load_json_object(overlays_path)
    reviews = _load_json_object(reviews_path)
    output_directory.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    evidence_counts = {
        "hud_frames": 0,
        "sprite_entities": 0,
        "deployment_points": 0,
        "events": 0,
        "status_onsets": 0,
    }
    previous_by_section: dict[tuple[str, str], np.ndarray] = {}
    for row in _frame_rows(source, canary_manifest.parent):
        path = row["path"]
        actual_sha = file_sha256(path)
        if actual_sha != row["declared_sha256"]:
            raise ValueError(f"frame hash mismatch: {path}")
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"could not decode frame: {path}")
        key = f"{row['video_id']}/{row['section']}/{path.name}"
        detected, reject_reason, metrics = detect_layout(image)
        sequence_key = (row["video_id"], row["section"])
        previous = previous_by_section.get(sequence_key)
        if previous is not None:
            metrics["hard_cut_score"] = _hard_cut_score(previous, image)
            if metrics["hard_cut_score"] >= 0.46:
                detected = None
                reject_reason = RejectReason.HARD_CUT
        previous_by_section[sequence_key] = image

        frame_overlays = overlays.get(key, {})
        if not isinstance(frame_overlays, dict):
            raise TypeError(f"overlay for {key} must be an object")
        evidence_counts["sprite_entities"] += len(frame_overlays.get("sprite_boxes", []))
        evidence_counts["deployment_points"] += len(frame_overlays.get("deployment_points", []))
        evidence_counts["events"] += len(frame_overlays.get("events", []))
        evidence_counts["status_onsets"] += len(frame_overlays.get("statuses", []))
        if frame_overlays.get("captions_overlap_arena") is True:
            detected = None
            reject_reason = RejectReason.CAPTIONS_OVER_ARENA

        rendered_path: Path | None = None
        rendered_sha: str | None = None
        if detected is not None:
            evidence_counts["hud_frames"] += 1
            rendered = render_audit(image, detected, frame_overlays)
            rendered_path = output_directory / f"{row['video_id']}_{row['section']}_{path.stem}_audit.jpg"
            if not cv2.imwrite(str(rendered_path), rendered, [cv2.IMWRITE_JPEG_QUALITY, 95]):
                raise RuntimeError(f"could not write {rendered_path}")
            rendered_sha = file_sha256(rendered_path)

        review_value = reviews.get(key)
        review = review_value if isinstance(review_value, dict) else None
        if reject_reason is None and review is None:
            reject_reason = RejectReason.MANUAL_REVIEW_REQUIRED
        elif reject_reason is None:
            assert review is not None
            review_reject = review.get("reject_reason")
            if review.get("decision") == "reject" and review_reject is not None:
                try:
                    reject_reason = RejectReason(str(review_reject))
                except ValueError as error:
                    raise ValueError(
                        f"manual review for {key} has unknown reject_reason "
                        f"{review_reject!r}"
                    ) from error
            required_true = (
                "grid_aligned",
                "clock_region_correct",
                "hand_next_elixir_regions_correct",
                "sprite_boxes_are_not_hitboxes",
                "deployment_overlay_correct",
                "status_overlay_correct",
            )
            if reject_reason is None and (
                review.get("decision") != "accept"
                or not all(review.get(name) is True for name in required_true)
            ):
                reject_reason = RejectReason.MANUAL_REVIEW_REJECTED

        records.append(
            {
                "key": key,
                "video_id": row["video_id"],
                "section": row["section"],
                "source": str(path),
                "source_sha256": actual_sha,
                "rendered": str(rendered_path) if rendered_path else None,
                "rendered_sha256": rendered_sha,
                "accepted": reject_reason is None,
                "reject_reason": reject_reason.value if reject_reason else None,
                "metrics": metrics,
                "layout": asdict(detected) if detected else None,
                "manual_review": review,
            }
        )

    minimums = {
        "hud_frames": 300,
        "sprite_entities": 300,
        "deployment_points": 30,
        "events": 50,
        "status_onsets": 20,
    }
    evidence_gate = {
        name: {
            "audited": evidence_counts[name],
            "minimum": minimum,
            "result": (
                "measurement_required"
                if evidence_counts[name] >= minimum
                else "insufficient_evidence"
            ),
        }
        for name, minimum in minimums.items()
    }
    payload = {
        "schema": OUTPUT_SCHEMA,
        "source_manifest": str(canary_manifest),
        "source_manifest_sha256": file_sha256(canary_manifest),
        "permission_provenance": {
            "basis": PERMISSION_BASIS,
            "public_cc_license_claimed": False,
            "note": "Permission is user-attested channel-owner approval, explicitly not a Creative Commons claim.",
        },
        "grid": {
            "columns": GRID_COLUMNS,
            "rows": GRID_ROWS,
            "normalized_arena_size": list(NORMALIZED_ARENA_SIZE),
            "normalized_grid_bounds": list(GRID_BOUNDS),
        },
        "replacement_gate_evidence": evidence_gate,
        "accepted": bool(records) and all(record["accepted"] for record in records),
        "records": records,
    }
    manifest_path = output_directory / "manifest.json"
    _atomic_write_json(manifest_path, payload)
    manifest_sha256 = file_sha256(manifest_path)
    (output_directory / "manifest.sha256").write_text(
        f"{manifest_sha256}  manifest.json\n", encoding="ascii"
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canary-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--overlays-json")
    parser.add_argument("--reviews-json")
    parser.add_argument("--bottom-actor-output-dir")
    parser.add_argument("--neutral-readiness-output-dir")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = audit_canary(
        canary_manifest=Path(args.canary_manifest).resolve(),
        output_directory=Path(args.output_dir).resolve(),
        overlays_path=Path(args.overlays_json).resolve() if args.overlays_json else None,
        reviews_path=Path(args.reviews_json).resolve() if args.reviews_json else None,
    )
    if args.bottom_actor_output_dir:
        payload["bottom_actor_export"] = export_bottom_actor_canary(
            canary_manifest=Path(args.canary_manifest).resolve(),
            output_directory=Path(args.bottom_actor_output_dir).resolve(),
        )
    if args.neutral_readiness_output_dir:
        payload["neutral_extraction_readiness"] = build_neutral_extraction_readiness(
            canary_manifest=Path(args.canary_manifest).resolve(),
            output_directory=Path(args.neutral_readiness_output_dir).resolve(),
        )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
