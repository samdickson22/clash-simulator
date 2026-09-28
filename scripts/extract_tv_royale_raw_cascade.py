from __future__ import annotations

# mypy: disable-error-code="import-not-found,import-untyped"
import argparse
import hashlib
import io
import json
import math
import subprocess
import time
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pyarrow.parquet as pq
import torch
from PIL import Image

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.causal_vision import CausalVisionTracker
from clasher.rl.oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256
from clasher.rl.public_action_mask import (
    PUBLIC_ACTION_MASK_CONTRACT_VERSION,
    PublicActionMaskBuilder,
    PublicActionMaskInput,
)
from clasher.rl.public_observation import (
    PUBLIC_OBSERVATION_SCHEMA_VERSION,
    REAL_PLAY_FEATURE_CONTRACT_VERSION,
)
from clasher.rl.replay_split import STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE
from clasher.rl.tv_royale_replay import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    SOURCE_ARENA_MIDDLE_Y,
    RecoveredTVRoyaleLocation,
    TVRoyaleDetection,
    TVRoyalePlacementConverter,
    recover_deployment_clock,
    recover_deployment_cost_bubble,
)
from clasher.rl.tv_royale_ui import (
    TVRoyaleUIExtractor,
    UIFrameState,
    UIPlayEvent,
    choose_sparse_noop_frames,
)
from clasher.spells import SPELL_REGISTRY, ProjectileSpell, RollingProjectileSpell
from scripts.import_tv_royale_placements import (
    _build_corpus,
    _combined_detections,
    _load_detector_models,
)

RAW_CROP_LEFT = 57
RAW_CROP_TOP = 137
LOCATION_FOLLOWUP_OFFSETS = (1, 2)
SPELL_DIAGNOSTIC_OFFSETS = (0, 1, 2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract sparse, state-conditioned TV Royale type/timing/no-op "
            "supervision from one raw replay"
        )
    )
    parser.add_argument("--input-parquet", required=True)
    parser.add_argument("--arena", required=True)
    parser.add_argument("--replay", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument(
        "--ui-template-root",
        default="datasets/external/CS541-Deep-Learning-Clash-Royale-Project",
    )
    parser.add_argument("--katacr-source-root", default="datasets/external/KataCR")
    parser.add_argument("--detector-weight", action="append", required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--parquet-batch-size", type=int, default=64)
    parser.add_argument("--deck-scan-stride", type=int, default=2)
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--nms-iou", type=float, default=0.6)
    parser.add_argument("--noop-stride", type=int, default=20)
    parser.add_argument("--noop-exclusion", type=int, default=5)
    parser.add_argument("--terminal-noop-exclusion", type=int, default=50)
    parser.add_argument("--max-entities", type=int, default=128)
    parser.add_argument("--audit-samples", type=int, default=12)
    parser.add_argument("--seed", type=int, default=1_044_101)
    return parser.parse_args()


def _decoded_frames(
    path: Path, *, batch_size: int, stride: int = 1
) -> Iterator[tuple[int, np.ndarray]]:
    if stride <= 0:
        raise ValueError("decode stride must be positive")
    row_index = 0
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(
        columns=["image"], batch_size=batch_size, use_threads=False
    ):
        for value in batch.column(0):
            if row_index % stride != 0:
                row_index += 1
                continue
            raw = value.as_py()["bytes"]
            image = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"))[
                ..., ::-1
            ].copy()
            yield row_index, image
            row_index += 1


def _selected_crops(
    path: Path, selected: set[int], *, batch_size: int
) -> dict[int, np.ndarray]:
    crops: dict[int, np.ndarray] = {}
    row_index = 0
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(
        columns=["image"], batch_size=batch_size, use_threads=False
    ):
        for value in batch.column(0):
            if row_index in selected:
                raw = value.as_py()["bytes"]
                image = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"))[
                    ..., ::-1
                ]
                crops[row_index] = image[
                    RAW_CROP_TOP : RAW_CROP_TOP + IMAGE_HEIGHT,
                    RAW_CROP_LEFT : RAW_CROP_LEFT + IMAGE_WIDTH,
                ].copy()
            row_index += 1
    missing = selected.difference(crops)
    if missing:
        raise ValueError(f"missing selected raw frames: {sorted(missing)[:10]}")
    return crops


def _detect(
    models: list[Any],
    crops: dict[int, np.ndarray],
    *,
    device: str,
    batch_size: int,
    confidence: float,
    nms_iou: float,
) -> dict[int, list[TVRoyaleDetection]]:
    output: dict[int, list[TVRoyaleDetection]] = {}
    frame_ids = sorted(crops)
    for start in range(0, len(frame_ids), batch_size):
        chunk_ids = frame_ids[start : start + batch_size]
        images = [crops[frame] for frame in chunk_ids]
        per_model_results = [
            model.predict(
                images,
                device=device,
                verbose=False,
                conf=confidence,
                iou=nms_iou,
                imgsz=(896, 576),
            )
            for model in models
        ]
        for local_index, frame in enumerate(chunk_ids):
            output[frame] = _combined_detections(
                [results[local_index] for results in per_model_results],
                models,
                nms_iou=nms_iou,
            )
    if device == "mps":
        torch.mps.synchronize()
    elif device == "cuda":
        torch.cuda.synchronize()
    return output


def _pin_template_source(root: Path) -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    digest = hashlib.sha256()
    files = sorted(
        (root / "cr_detection" / "cards").glob("*.png")
    ) + sorted((root / "cr_detection" / "elixir").glob("*.png"))
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return {
        "git_revision": revision,
        "template_files": len(files),
        "template_sha256": digest.hexdigest(),
    }


def _build_public_state_v2_sidecar(
    *,
    corpus_payload: dict[str, np.ndarray],
    rows: list[dict[str, Any]],
    converter: TVRoyalePlacementConverter,
    state_by_frame: dict[int, UIFrameState],
    crops: dict[int, np.ndarray],
    detections: dict[int, list[TVRoyaleDetection]],
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Build an observation-only v2 sidecar aligned to the legacy corpus."""

    row_by_key = {
        (int(item["source_index"]), int(item["frame"])): item for item in rows
    }
    arrays: dict[str, list[np.ndarray]] = {
        name: []
        for name in (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "entity_id_confidence",
            "entity_feature_confidence",
            "hand_ids",
            "hand_id_confidence",
            "global_features",
            "global_feature_confidence",
            "opponent_history_ids",
            "opponent_history_ages",
            "opponent_history_confidence",
            "opponent_seen_card_ids",
            "opponent_seen_card_confidence",
            "action_masks",
        )
    }
    source_indices = corpus_payload["source_indices"].astype(np.int64, copy=False)
    source_frames = corpus_payload["source_frames"].astype(np.int64, copy=False)
    public_by_frame: dict[int, Any] = {}
    tracker = CausalVisionTracker()
    mask_builder = PublicActionMaskBuilder(converter.builder)
    expert_action_masked = np.zeros((source_frames.size,), dtype=np.bool_)
    needed_frames = set(source_frames.tolist())
    tracking_frames = sorted(
        set(detections).intersection(crops).intersection(state_by_frame)
    )
    if not needed_frames.issubset(tracking_frames):
        missing = sorted(needed_frames.difference(tracking_frames))
        raise ValueError(f"public-state tracking frames are missing: {missing[:10]}")
    for frame in tracking_frames:
        state = state_by_frame[frame]
        if state.elixir is None:
            raise ValueError(f"public-state frame {frame} has no elixir")
        frame_public = converter.public_observation(
            image_bgr=crops[frame],
            raw_hand=state.hand,
            elixir=state.elixir,
            frame=frame,
            detections=detections[frame],
            raw_next_card=state.next_card,
        )
        tracked = tracker.update(frame_public, frame=frame)
        if frame in needed_frames:
            public_by_frame[frame] = tracked

    expert_actions = corpus_payload["expert_actions"].astype(np.int64, copy=False)
    for row_index, (source_index, frame) in enumerate(
        zip(source_indices.tolist(), source_frames.tolist())
    ):
        key = (source_index, frame)
        if key not in row_by_key:
            raise ValueError(f"public-state sidecar cannot resolve corpus row {key}")
        public = public_by_frame[frame]
        observation = public.observation
        action_mask = mask_builder.build(
            PublicActionMaskInput.from_confidence_observation(public)
        )
        expert_action = int(expert_actions[row_index])
        if not action_mask[expert_action]:
            # Preserve label validity separately; policy input cannot depend on
            # the action it is supposed to predict.
            expert_action_masked[row_index] = True
        arrays["action_masks"].append(action_mask)
        for name in (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "hand_ids",
            "global_features",
            "opponent_history_ids",
            "opponent_history_ages",
            "opponent_seen_card_ids",
        ):
            arrays[name].append(getattr(observation, name))
        for name in (
            "entity_id_confidence",
            "entity_feature_confidence",
            "hand_id_confidence",
            "global_feature_confidence",
            "opponent_history_confidence",
            "opponent_seen_card_confidence",
        ):
            arrays[name].append(getattr(public, name))

    payload = {name: np.stack(values) for name, values in arrays.items()}
    payload.update(
        {
            "source_indices": source_indices.copy(),
            "source_frames": source_frames.copy(),
            "expert_actions": expert_actions.copy(),
            "expert_action_masked": expert_action_masked,
            "schema_version": np.asarray(PUBLIC_OBSERVATION_SCHEMA_VERSION),
            "feature_contract_version": np.asarray(
                REAL_PLAY_FEATURE_CONTRACT_VERSION
            ),
            "action_mask_contract_version": np.asarray(
                PUBLIC_ACTION_MASK_CONTRACT_VERSION
            ),
        }
    )
    hp_confidence = payload["entity_feature_confidence"][..., 9]
    visible_entities = payload["entity_mask"].astype(np.bool_, copy=False)
    observed_hp = (hp_confidence > 0.0) & visible_entities
    motion_confidence = payload["entity_feature_confidence"][..., 27]
    observed_motion = (motion_confidence > 0.0) & visible_entities
    tower_hp_confidence = payload["global_feature_confidence"][:, 8:14]
    effect_entities = (payload["entity_features"][..., 7] > 0.5) & visible_entities
    statistics = {
        "schema": "confidence-aware-public-observation-v2",
        "schema_version": PUBLIC_OBSERVATION_SCHEMA_VERSION,
        "feature_contract_version": REAL_PLAY_FEATURE_CONTRACT_VERSION,
        "action_mask_contract_version": PUBLIC_ACTION_MASK_CONTRACT_VERSION,
        "temporal_tracker": "causal-vision-v1",
        "samples": int(source_frames.size),
        "visible_entities": int(visible_entities.sum()),
        "entities_with_measured_hp": int(observed_hp.sum()),
        "entity_hp_coverage": float(
            observed_hp.sum() / max(1, int(visible_entities.sum()))
        ),
        "mean_observed_hp_confidence": (
            float(hp_confidence[observed_hp].mean()) if observed_hp.any() else 0.0
        ),
        "entities_with_motion_direction": int(observed_motion.sum()),
        "motion_direction_coverage": float(
            observed_motion.sum() / max(1, int(visible_entities.sum()))
        ),
        "tower_hp_measurements": int(np.count_nonzero(tower_hp_confidence > 0.0)),
        "visually_confirmed_effect_entities": int(effect_entities.sum()),
        "expert_mask_recoveries": 0,
        "expert_actions_masked_by_public_state": int(expert_action_masked.sum()),
        "label_conditioned_mask_mutations": 0,
        "legacy_corpus_mutated": False,
    }
    return payload, statistics


def _unambiguous_events(
    events: list[UIPlayEvent],
    state_by_frame: dict[int, UIFrameState],
    converter: TVRoyalePlacementConverter,
) -> tuple[list[UIPlayEvent], dict[str, int]]:
    counts = Counter(event.frame for event in events)
    accepted: list[UIPlayEvent] = []
    rejected: Counter[str] = Counter()
    for event in events:
        if event.card.startswith("gray_"):
            rejected["gray_card_event"] += 1
            continue
        if counts[event.frame] != 1:
            rejected["multiple_actions_same_frame"] += 1
            continue
        state = state_by_frame.get(event.frame)
        if state is None or state.elixir is None or any(
            card is None for card in state.hand
        ):
            rejected["incomplete_ui_state"] += 1
            continue
        target = converter.source_card_name(event.card)
        if target is None:
            rejected["outside_enabled_vocabulary"] += 1
            continue
        hand_names = [converter.source_card_name(card) for card in state.hand]
        if target not in hand_names:
            rejected["target_not_in_hand"] += 1
            continue
        accepted.append(event)
    return accepted, dict(sorted(rejected.items()))


def _recover_consistent_location(
    event: UIPlayEvent,
    detections: dict[int, list[TVRoyaleDetection]],
    converter: TVRoyalePlacementConverter,
    *,
    followup_offsets: tuple[int, ...] = LOCATION_FOLLOWUP_OFFSETS,
) -> tuple[RecoveredTVRoyaleLocation | None, str | None]:
    """Backward-compatible wrapper for strict offline deployment evidence."""

    location, reason, _kind, _evidence_frame = (
        _recover_consistent_location_evidence(
            event,
            detections,
            converter,
            followup_offsets=followup_offsets,
        )
    )
    return location, reason


def _recover_consistent_location_evidence(
    event: UIPlayEvent,
    detections: dict[int, list[TVRoyaleDetection]],
    converter: TVRoyalePlacementConverter,
    *,
    followup_offsets: tuple[int, ...] = LOCATION_FOLLOWUP_OFFSETS,
) -> tuple[RecoveredTVRoyaleLocation | None, str | None, str, int | None]:
    """Fuse adjacent-frame clock and cost-bubble evidence for an offline label.

    The two-frame deployment clock remains mandatory.  A public floating-cost
    bubble is an independent anchor: if present it must agree at canonical-tile
    level or the label fails closed.  Future evidence is returned with explicit
    provenance and must never be placed in a live current-frame observation.
    """

    if converter.source_card_type(event.card) == "spell":
        return None, "spell_clock_not_expected", "none", None
    before = detections.get(event.frame)
    if before is None:
        return None, "missing_event_frame", "none", None
    clocks: list[RecoveredTVRoyaleLocation] = []
    bubbles: list[RecoveredTVRoyaleLocation] = []
    bubble_frames: list[int] = []
    for offset in followup_offsets:
        after = detections.get(event.frame + offset)
        if after is None:
            continue
        clock = recover_deployment_clock(before, after)
        if clock is not None and clock.y > SOURCE_ARENA_MIDDLE_Y:
            clocks.append(clock)
        bubble = recover_deployment_cost_bubble(before, after)
        if bubble is not None and bubble.y > SOURCE_ARENA_MIDDLE_Y:
            bubbles.append(bubble)
            bubble_frames.append(event.frame + offset)
    if len(clocks) != len(followup_offsets):
        return None, "clock_missing_followup", "none", None
    clock_tiles = {
        converter.source_pixel_to_canonical_tile(round(item.x), round(item.y))
        for item in clocks
    }
    if len(clock_tiles) != 1:
        return None, "inconsistent_clock_tiles", "none", None
    if not bubbles:
        return (
            max(clocks, key=lambda item: (item.confidence, item.support)),
            None,
            "deployment-clock",
            event.frame + followup_offsets[0],
        )

    bubble_tiles = {
        converter.source_pixel_to_canonical_tile(round(item.x), round(item.y))
        for item in bubbles
    }
    if len(bubble_tiles) != 1:
        return None, "inconsistent_cost_bubble_tiles", "none", None
    if bubble_tiles != clock_tiles:
        return None, "cost_bubble_clock_disagreement", "none", None

    anchors = clocks + bubbles
    weight = sum(item.confidence for item in anchors)
    fused = RecoveredTVRoyaleLocation(
        x=sum(item.x * item.confidence for item in anchors) / weight,
        y=sum(item.y * item.confidence for item in anchors) / weight,
        confidence=min(item.confidence for item in anchors),
        support=sum(item.support for item in anchors),
    )
    return fused, None, "deployment-clock+cost-bubble", bubble_frames[0]


def _persistent_area_spell(
    event: UIPlayEvent, converter: TVRoyalePlacementConverter
) -> bool:
    card = converter.source_card_name(event.card)
    spell = SPELL_REGISTRY.get(card) if card is not None else None
    return bool(
        spell is not None
        and not isinstance(spell, (ProjectileSpell, RollingProjectileSpell))
        and float(getattr(spell, "duration", 0.0) or 0.0) > 0.0
    )


def _recover_consistent_spell_location(
    event: UIPlayEvent,
    detections: dict[int, list[TVRoyaleDetection]],
    converter: TVRoyalePlacementConverter,
    *,
    followup_offsets: tuple[int, ...] = LOCATION_FOLLOWUP_OFFSETS,
    minimum_confidence: float = 0.55,
    existing_match_distance: float = 24.0,
) -> tuple[RecoveredTVRoyaleLocation | None, str | None]:
    """Recover one new, stable persistent-area spell visual fail-closed."""

    if not _persistent_area_spell(event, converter):
        return None, "spell_visual_not_persistent_area"

    def spell_centers(frame: int) -> list[tuple[float, float, float]]:
        return [
            (
                (detection.x1 + detection.x2) * 0.5,
                (detection.y1 + detection.y2) * 0.5,
                detection.confidence,
            )
            for detection in detections.get(frame, ())
            if detection.confidence >= minimum_confidence
            and converter.source_card_type(detection.class_name) == "spell"
        ]

    before = spell_centers(event.frame)
    recovered: list[tuple[float, float, float]] = []
    for offset in followup_offsets:
        novel = [
            point
            for point in spell_centers(event.frame + offset)
            if not any(
                math.hypot(point[0] - old[0], point[1] - old[1])
                <= existing_match_distance
                for old in before
            )
        ]
        if len(novel) != 1:
            return None, "spell_visual_not_unique"
        recovered.append(novel[0])
    if len(recovered) != len(followup_offsets):
        return None, "spell_visual_missing_followup"
    tiles = {
        converter.source_pixel_to_canonical_tile(round(x), round(y))
        for x, y, _ in recovered
    }
    if len(tiles) != 1:
        return None, "inconsistent_spell_visual_tiles"
    weight = sum(confidence for _, _, confidence in recovered)
    return (
        RecoveredTVRoyaleLocation(
            x=sum(x * confidence for x, _, confidence in recovered) / weight,
            y=sum(y * confidence for _, y, confidence in recovered) / weight,
            confidence=max(confidence for _, _, confidence in recovered),
            support=len(recovered),
        ),
        None,
    )


def _spell_detection_windows(
    events: list[UIPlayEvent],
    detections: dict[int, list[TVRoyaleDetection]],
    converter: TVRoyalePlacementConverter,
    *,
    offsets: tuple[int, ...] = SPELL_DIAGNOSTIC_OFFSETS,
) -> dict[str, Any]:
    """Serialize spell-class detections for later localization research.

    This is diagnostic-only evidence: it never creates a spatial label.  A
    future spell extractor must prove which detected visual corresponds to the
    source player's aim point rather than assuming any sprite box is a target.
    """
    windows: dict[str, Any] = {}
    for event in events:
        if converter.source_card_type(event.card) != "spell":
            continue
        frames: dict[str, Any] = {}
        for offset in offsets:
            frame = event.frame + offset
            if frame not in detections:
                continue
            spell_detections = [
                detection
                for detection in detections[frame]
                if converter.source_card_type(detection.class_name) == "spell"
            ]
            frames[str(frame)] = [
                {
                    "class_name": detection.class_name,
                    "belonging": detection.belonging,
                    "confidence": detection.confidence,
                    "xyxy": [
                        detection.x1,
                        detection.y1,
                        detection.x2,
                        detection.y2,
                    ],
                }
                for detection in spell_detections
            ]
        windows[str(event.frame)] = {"card": event.card, "frames": frames}
    return windows


def _draw_grid(image: np.ndarray) -> None:
    for column in range(19):
        x = round(column * IMAGE_WIDTH / 18)
        cv2.line(image, (x, 0), (x, IMAGE_HEIGHT), (110, 110, 110), 1)
    grid_height = IMAGE_HEIGHT - 62 - 7
    for row in range(33):
        y = round(62 + row * grid_height / 32)
        cv2.line(image, (0, y), (IMAGE_WIDTH, y), (110, 110, 110), 1)
    river = round(62 + 16 * grid_height / 32)
    cv2.line(image, (0, river), (IMAGE_WIDTH, river), (0, 255, 255), 2)


def _select_audit_frames(
    frames: list[int],
    labels: dict[int, list[str]],
    *,
    samples: int,
) -> list[int]:
    """Prefer accepted labels while retaining temporal coverage as fallback."""
    if samples <= 0 or not frames:
        return []

    limit = min(samples, len(frames))

    def spaced(values: list[int], count: int) -> list[int]:
        if count <= 0 or not values:
            return []
        indices = np.linspace(
            0,
            len(values) - 1,
            min(count, len(values)),
            dtype=np.int64,
        )
        return [values[int(index)] for index in indices]

    labeled = [frame for frame in frames if labels.get(frame)]
    selected = spaced(labeled, limit)
    if len(selected) < limit:
        remaining = [frame for frame in frames if frame not in set(selected)]
        selected.extend(spaced(remaining, limit - len(selected)))
    return sorted(selected)


def _render_audit(
    output_dir: Path,
    crops: dict[int, np.ndarray],
    detections: dict[int, list[TVRoyaleDetection]],
    labels: dict[int, list[str]],
    state_by_frame: dict[int, UIFrameState],
    locations: dict[int, RecoveredTVRoyaleLocation],
    location_kinds: dict[int, str],
    location_evidence_frames: dict[int, int],
    *,
    samples: int,
) -> list[str]:
    if samples <= 0 or not crops:
        return []
    frames = sorted(crops)
    selected = _select_audit_frames(frames, labels, samples=samples)
    for kind in sorted(set(location_kinds.values())):
        if any(location_kinds.get(frame) == kind for frame in selected):
            continue
        candidates = [
            frame for frame in frames if location_kinds.get(frame) == kind
        ]
        if candidates:
            selected.append(candidates[len(candidates) // 2])
    selected = sorted(set(selected))
    audit_dir = output_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for audit_index, frame in enumerate(selected):
        evidence_frame = location_evidence_frames.get(frame, frame)
        panel = crops[evidence_frame].copy()
        _draw_grid(panel)
        for detection in detections[evidence_frame]:
            color = (0, 210, 0) if detection.belonging == 0 else (0, 90, 255)
            cv2.rectangle(
                panel,
                (round(detection.x1), round(detection.y1)),
                (round(detection.x2), round(detection.y2)),
                color,
                1,
            )
            center = (
                round((detection.x1 + detection.x2) * 0.5),
                round((detection.y1 + detection.y2) * 0.5),
            )
            cv2.circle(panel, center, 2, color, -1)
        location = locations.get(frame)
        if location is not None:
            location_kind = location_kinds[frame]
            marker_color = (
                (40, 255, 40)
                if location_kind == "deployment-clock"
                else (
                    (40, 240, 255)
                    if location_kind == "deployment-clock+cost-bubble"
                    else (255, 220, 40)
                )
            )
            point = (round(location.x), round(location.y))
            cv2.drawMarker(
                panel,
                point,
                marker_color,
                cv2.MARKER_CROSS,
                18,
                2,
            )
            cv2.putText(
                panel,
                location_kind,
                (max(2, point[0] - 58), max(14, point[1] - 12)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                marker_color,
                1,
                cv2.LINE_AA,
            )
        state = state_by_frame[frame]
        header = np.zeros((74, IMAGE_WIDTH, 3), dtype=np.uint8)
        cv2.putText(
            header,
            f"event={frame} evidence={evidence_frame} label={'+'.join(labels.get(frame, ['candidate-rejected']))} elixir={state.elixir:.2f}",
            (5, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            header,
            "hand=" + ",".join(str(card) for card in state.hand),
            (5, 42),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (225, 225, 225),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            header,
            "boxes=sprites; cross=offline clock/bubble/area anchor (not a hitbox)",
            (5, 64),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (0, 220, 255),
            1,
            cv2.LINE_AA,
        )
        canvas = np.concatenate((header, panel), axis=0)
        output = audit_dir / f"{audit_index:03d}_frame_{frame:05d}.jpg"
        if not cv2.imwrite(str(output), canvas, [cv2.IMWRITE_JPEG_QUALITY, 94]):
            raise OSError(f"failed to write audit image {output}")
        outputs.append(str(output))
    return outputs


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0 or args.parquet_batch_size <= 0:
        raise ValueError("batch sizes must be positive")
    if args.deck_scan_stride <= 0:
        raise ValueError("deck scan stride must be positive")
    source = resolve_path(args.input_parquet, must_exist=True)
    output_dir = resolve_path(args.output_dir) / args.arena / args.replay
    output_dir.mkdir(parents=True, exist_ok=True)
    template_root = resolve_path(args.ui_template_root, must_exist=True)
    converter = TVRoyalePlacementConverter(
        decks_path=str(resolve_decks_path(args.decks_path, must_exist=True)),
        max_entities=args.max_entities,
    )
    extractor = TVRoyaleUIExtractor(
        template_root,
        card_cost_resolver=converter.source_card_cost,
    )

    started = time.perf_counter()
    deck_started = time.perf_counter()
    deck = extractor.discover_deck(
        image
        for _, image in _decoded_frames(
            source,
            batch_size=args.parquet_batch_size,
            stride=args.deck_scan_stride,
        )
    )
    deck_seconds = time.perf_counter() - deck_started

    state_started = time.perf_counter()
    states, raw_events = extractor.scan_states(
        _decoded_frames(source, batch_size=args.parquet_batch_size), deck
    )
    state_seconds = time.perf_counter() - state_started
    state_by_frame = {state.frame: state for state in states}
    events, event_rejections = _unambiguous_events(
        raw_events, state_by_frame, converter
    )
    noop_frames = choose_sparse_noop_frames(
        states,
        events,
        stride_frames=args.noop_stride,
        exclusion_frames=args.noop_exclusion,
        terminal_exclusion_frames=args.terminal_noop_exclusion,
    )
    available_frames = set(state_by_frame)
    location_followup_frames = {
        event.frame + offset
        for event in events
        if converter.source_card_type(event.card) != "spell"
        for offset in LOCATION_FOLLOWUP_OFFSETS
        if event.frame + offset in available_frames
    }
    spell_diagnostic_frames = {
        event.frame + offset
        for event in events
        if converter.source_card_type(event.card) == "spell"
        for offset in SPELL_DIAGNOSTIC_OFFSETS
        if event.frame + offset in available_frames
    }
    selected_frames = (
        {event.frame for event in events}
        .union(noop_frames)
        .union(location_followup_frames)
        .union(spell_diagnostic_frames)
    )
    supervision_frames = {event.frame for event in events}.union(noop_frames)
    motion_predecessor_frames = {
        frame - 1
        for frame in supervision_frames
        if frame > 0 and frame - 1 in available_frames
    }
    selected_frames.update(motion_predecessor_frames)

    selection_started = time.perf_counter()
    crops = _selected_crops(
        source, selected_frames, batch_size=args.parquet_batch_size
    )
    selection_seconds = time.perf_counter() - selection_started
    model_load_started = time.perf_counter()
    weights = [resolve_path(value, must_exist=True) for value in args.detector_weight]
    models = _load_detector_models(
        weights, resolve_path(args.katacr_source_root, must_exist=True)
    )
    model_load_seconds = time.perf_counter() - model_load_started
    detector_started = time.perf_counter()
    detections = _detect(
        models,
        crops,
        device=args.device,
        batch_size=args.batch_size,
        confidence=args.confidence,
        nms_iou=args.nms_iou,
    )
    detector_seconds = time.perf_counter() - detector_started

    rows: list[dict[str, Any]] = []
    location_rows: list[dict[str, Any]] = []
    conversion_rejections: Counter[str] = Counter()
    location_rejections: Counter[str] = Counter()
    recovered_locations: dict[int, RecoveredTVRoyaleLocation] = {}
    recovered_location_kinds: dict[int, str] = {}
    recovered_location_evidence_frames: dict[int, int] = {}
    labels: dict[int, list[str]] = {}
    source_index = 0
    for event in events:
        state = state_by_frame[event.frame]
        assert state.elixir is not None
        converted = converter.convert_type_only(
            raw_card=event.card,
            raw_hand=state.hand,
            elixir=state.elixir,
            frame=event.frame,
            detections=detections[event.frame],
        )
        if converted is None:
            conversion_rejections["type_conversion_failed"] += 1
            continue
        rows.append(
            {
                "source_index": source_index,
                "arena": args.arena,
                "replay": args.replay,
                "frame": event.frame,
                "converted": converted,
            }
        )
        labels.setdefault(event.frame, []).append(f"type:{event.card}")
        is_spell = converter.source_card_type(event.card) == "spell"
        location_evidence_frame: int | None
        if is_spell:
            location, location_reason = _recover_consistent_spell_location(
                event, detections, converter
            )
            location_kind = "persistent-area-center"
            location_evidence_frame = event.frame + LOCATION_FOLLOWUP_OFFSETS[0]
        else:
            (
                location,
                location_reason,
                location_kind,
                location_evidence_frame,
            ) = _recover_consistent_location_evidence(
                event,
                detections,
                converter,
            )
        if location is None:
            location_rejections[location_reason or "location_recovery_failed"] += 1
        else:
            location_x = round(location.x)
            location_y = round(location.y)
            validation = (
                converter.is_spell_location_training_candidate
                if is_spell
                else converter.is_location_training_candidate
            )
            location_valid, location_reason = validation(
                raw_card=event.card,
                raw_hand=state.hand,
                elixir=state.elixir,
                x=location_x,
                y=location_y,
            )
            location_converted = (
                converter.convert(
                    raw_card=event.card,
                    raw_hand=state.hand,
                    elixir=state.elixir,
                    frame=event.frame,
                    x=location_x,
                    y=location_y,
                    detections=detections[event.frame],
                )
                if location_valid
                else None
            )
            if location_converted is None:
                location_rejections[
                    location_reason or "location_conversion_failed"
                ] += 1
            else:
                location_rows.append(
                    {
                        "source_index": source_index,
                        "arena": args.arena,
                        "replay": args.replay,
                        "frame": event.frame,
                        "converted": location_converted,
                    }
                )
                recovered_locations[event.frame] = location
                recovered_location_kinds[event.frame] = location_kind
                recovered_location_evidence_frames[event.frame] = int(
                    location_evidence_frame
                    if location_evidence_frame is not None
                    else event.frame + LOCATION_FOLLOWUP_OFFSETS[0]
                )
                labels[event.frame].append(
                    "location:"
                    f"{event.card}@{location_converted.expert_action % 576}"
                )
        source_index += 1
    for frame in noop_frames:
        state = state_by_frame[frame]
        assert state.elixir is not None
        converted = converter.convert_noop(
            raw_card="None",
            raw_hand=state.hand,
            elixir=state.elixir,
            frame=frame,
            detections=detections[frame],
        )
        if converted is None:
            conversion_rejections["noop_conversion_failed"] += 1
            continue
        rows.append(
            {
                "source_index": source_index,
                "arena": args.arena,
                "replay": args.replay,
                "frame": frame,
                "converted": converted,
            }
        )
        labels.setdefault(frame, []).append("noop")
        source_index += 1
    payload, corpus_statistics = _build_corpus(
        rows,
        converter=converter,
        source_path=source,
        seed=args.seed,
        label_source="tv-royale-raw-cascade-type-only-v1",
    )
    corpus_path = output_dir / "corpus.npz"
    atomic_save_npz(corpus_path, payload)
    public_state_payload, public_state_statistics = _build_public_state_v2_sidecar(
        corpus_payload=payload,
        rows=rows,
        converter=converter,
        state_by_frame=state_by_frame,
        crops=crops,
        detections=detections,
    )
    public_state_path = output_dir / "public_state_v2.npz"
    atomic_save_npz(public_state_path, public_state_payload)
    location_corpus: dict[str, Any] | None = None
    if location_rows:
        location_payload, location_statistics = _build_corpus(
            location_rows,
            converter=converter,
            source_path=source,
            seed=args.seed,
            label_source=STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE,
        )
        location_corpus_path = output_dir / "location_corpus.npz"
        atomic_save_npz(location_corpus_path, location_payload)
        location_corpus = {
            "path": str(location_corpus_path),
            "sha256": file_sha256(location_corpus_path),
            "statistics": location_statistics,
        }
    spell_detection_windows = _spell_detection_windows(events, detections, converter)
    audit_outputs = _render_audit(
        output_dir,
        crops,
        detections,
        labels,
        state_by_frame,
        recovered_locations,
        recovered_location_kinds,
        recovered_location_evidence_frames,
        samples=args.audit_samples,
    )
    total_seconds = time.perf_counter() - started
    manifest = {
        "schema": "tv-royale-raw-cascade-v1",
        "arena": args.arena,
        "replay": args.replay,
        "source": str(source),
        "source_sha256": file_sha256(source),
        "frames": len(states),
        "deck": sorted(deck),
        "raw_events": len(raw_events),
        "accepted_type_events": sum(
            1 for values in labels.values() for value in values if value.startswith("type:")
        ),
        "accepted_noops": sum(
            1 for values in labels.values() for value in values if value == "noop"
        ),
        "event_rejections": event_rejections,
        "conversion_rejections": dict(sorted(conversion_rejections.items())),
        "location_rejections": dict(sorted(location_rejections.items())),
        "selected_vision_frames": len(selected_frames),
        "motion_predecessor_frames": len(motion_predecessor_frames),
        "detections": sum(len(value) for value in detections.values()),
        "supervision": {
            "played_cards": "type-head-v1 only; location_loss_coef=0",
            "noops": "exact",
            "spatial_labels": len(location_rows),
            "spatial_label_contract": (
                "lower-player troop/building deployment clock or new stable "
                "mechanics-defined persistent-area spell visual; a public "
                "floating-cost bubble is fused when present and must agree; "
                "two adjacent frames must agree on one legal canonical tile; "
                "all future-frame evidence is offline-teacher label-only"
            ),
            "live_policy_input_before_observation": False,
        },
        "noop_sampling": {
            "stride_frames": args.noop_stride,
            "event_exclusion_frames": args.noop_exclusion,
            "terminal_exclusion_frames": args.terminal_noop_exclusion,
        },
        "timing_seconds": {
            "deck_discovery": deck_seconds,
            "ui_state_scan": state_seconds,
            "selected_frame_decode": selection_seconds,
            "detector_model_load": model_load_seconds,
            "sparse_detector": detector_seconds,
            "total_excluding_source_download": total_seconds,
        },
        "throughput": {
            "selected_detector_fps": len(selected_frames) / detector_seconds,
            "local_games_per_hour": 3600.0 / total_seconds,
        },
        "detector": {
            "device": args.device,
            "batch_size": args.batch_size,
            "confidence": args.confidence,
            "nms_iou": args.nms_iou,
            "weights": [
                {"path": str(path), "sha256": file_sha256(path)} for path in weights
            ],
        },
        "ui_templates": _pin_template_source(template_root),
        "card_cost_authority": {
            "source": "packaged-gamedata",
            "path": str(converter.builder.loader.data_file),
            "sha256": file_sha256(converter.builder.loader.data_file),
        },
        "deck_scan_stride": args.deck_scan_stride,
        "corpus": {
            "path": str(corpus_path),
            "sha256": file_sha256(corpus_path),
            "statistics": corpus_statistics,
        },
        "public_state_v2": {
            "path": str(public_state_path),
            "sha256": file_sha256(public_state_path),
            "statistics": public_state_statistics,
        },
        "location_corpus": location_corpus,
        "spell_detection_windows": spell_detection_windows,
        "audit_outputs": audit_outputs,
        "accepted_labels": {
            str(frame): values for frame, values in sorted(labels.items())
        },
        "placement_evidence": {
            str(frame): {
                "mode": "offline-teacher",
                "label_only": True,
                "live_policy_input_before_observation": False,
                "event_frame": frame,
                "evidence_frame": recovered_location_evidence_frames[frame],
                "kind": recovered_location_kinds[frame],
                "x": recovered_locations[frame].x,
                "y": recovered_locations[frame].y,
                "confidence": recovered_locations[frame].confidence,
                "support": recovered_locations[frame].support,
            }
            for frame in sorted(recovered_locations)
        },
    }
    manifest_path = output_dir / "manifest.json"
    atomic_write_json(manifest_path, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
