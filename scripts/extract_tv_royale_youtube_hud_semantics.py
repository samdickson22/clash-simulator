from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import copy
import gzip
import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from scripts.extract_tv_royale_youtube_fullmatch import (
    HUD_ROIS,
    _atomic_gzip_jsonl,
    _atomic_json,
    _crop_relative,
    _sha256,
)

SCHEMA = "clasher.youtube.current_frame_hud_semantics.v1"


def _rows(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _visual_features(crop: np.ndarray) -> dict[str, Any]:
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    height, width = crop.shape[:2]
    purple = (
        (hsv[:, :, 0] >= 125)
        & (hsv[:, :, 0] <= 170)
        & (hsv[:, :, 1] >= 90)
        & (hsv[:, :, 2] >= 80)
    )
    gold = (
        (hsv[:, :, 0] >= 8)
        & (hsv[:, :, 0] <= 38)
        & (hsv[:, :, 1] >= 100)
        & (hsv[:, :, 2] >= 100)
    )
    grayscale = hsv[:, :, 1] <= 42
    border = np.zeros((height, width), dtype=np.bool_)
    border_width = max(2, round(min(height, width) * 0.10))
    border[:border_width] = True
    border[-border_width:] = True
    border[:, :border_width] = True
    border[:, -border_width:] = True
    top_height = max(1, round(height * 0.20))
    top = purple[:top_height].astype(np.uint8) * 255
    components, _, stats, _ = cv2.connectedComponentsWithStats(top)
    diamonds = []
    for component in range(1, components):
        x, y, box_width, box_height, area = stats[component]
        center_x = (x + box_width * 0.5) / width
        if (
            0.15 <= center_x <= 0.80
            and 0.08 * width <= box_width <= 0.25 * width
            and 0.06 * height <= box_height <= 0.18 * height
            and area >= 0.004 * height * width
        ):
            diamonds.append(
                {
                    "box_normalized": [
                        x / width,
                        y / height,
                        (x + box_width) / width,
                        (y + box_height) / height,
                    ],
                    "area": int(area),
                }
            )
    return {
        "grayscale_fraction": float(np.mean(grayscale)),
        "mean_saturation": float(np.mean(hsv[:, :, 1]) / 255.0),
        "mean_value": float(np.mean(hsv[:, :, 2]) / 255.0),
        "purple_border_fraction": float(np.mean(purple[border])),
        "gold_border_fraction": float(np.mean(gold[border])),
        "top_purple_fraction": float(np.mean(purple[:top_height])),
        "diamond_components": diamonds,
    }


def _disabled_head(features: dict[str, Any]) -> dict[str, Any]:
    grayscale = float(features["grayscale_fraction"])
    saturation = float(features["mean_saturation"])
    if grayscale >= 0.65 and saturation <= 0.22:
        confidence = min(1.0, (grayscale - 0.50) / 0.35)
        return {
            "value": True,
            "valid": True,
            "confidence": confidence,
            "reason": None,
            "evidence": "current_frame_grayscale_card_state",
        }
    if grayscale <= 0.30 and saturation >= 0.30:
        confidence = min(1.0, (0.45 - grayscale) / 0.35)
        return {
            "value": False,
            "valid": True,
            "confidence": confidence,
            "reason": None,
            "evidence": "current_frame_color_card_state",
        }
    return {
        "value": None,
        "valid": False,
        "confidence": 0.0,
        "reason": "ambiguous_grayscale_or_overlay_state",
        "evidence": "current_frame_card_pixels",
    }


def _variant_head(
    features: dict[str, Any], identity_head: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    purple_border = float(features["purple_border_fraction"])
    gold_border = float(features["gold_border_fraction"])
    top_purple = float(features["top_purple_fraction"])
    diamonds = len(features["diamond_components"])
    displayed_cost = identity_head.get("displayed_cost", {})
    identity_candidate = identity_head.get("candidate")
    cost_two = bool(
        displayed_cost.get("valid") and displayed_cost.get("value") == 2
    )
    hero_candidate = bool(
        identity_candidate == "card_action:Barbarians"
        or (cost_two and gold_border >= 0.35)
    )
    evolution_ready = bool(purple_border >= 0.45 and top_purple >= 0.35)
    progress_valid = bool(
        not evolution_ready and 0.12 <= top_purple <= 0.35 and 1 <= diamonds <= 3
    )
    ready_head = {
        "value": evolution_ready,
        "valid": bool(evolution_ready or purple_border <= 0.30),
        "confidence": (
            min(1.0, purple_border / 0.55)
            if evolution_ready
            else min(1.0, (0.45 - purple_border) / 0.30)
        ),
        "reason": None if evolution_ready or purple_border <= 0.30 else "ambiguous_purple_frame",
        "evidence": "current_frame_purple_frame",
    }
    progress_head = {
        "value": diamonds if progress_valid else None,
        "valid": progress_valid,
        "confidence": min(1.0, top_purple / 0.25) if progress_valid else 0.0,
        "reason": None if progress_valid else "no_calibrated_progress_diamonds",
        "evidence": "current_frame_top_purple_diamond_components",
    }
    if evolution_ready:
        variant = {
            "value": "evolution_ready",
            "candidate": "evolution_ready",
            "valid": True,
            "confidence": ready_head["confidence"],
            "reason": None,
            "exact_card_identity_separate": True,
        }
    elif progress_valid:
        variant = {
            "value": "evolution_progress",
            "candidate": "evolution_progress",
            "valid": True,
            "confidence": progress_head["confidence"],
            "reason": None,
            "exact_card_identity_separate": True,
        }
    elif hero_candidate:
        variant = {
            "value": None,
            "candidate": "hero_variant",
            "valid": False,
            "confidence": float(displayed_cost.get("confidence", 0.0)),
            "reason": "hero_art_authority_not_proven",
            "exact_card_identity_separate": True,
        }
    elif purple_border <= 0.15 and top_purple <= 0.08:
        variant = {
            "value": "base_or_ordinary",
            "candidate": "base_or_ordinary",
            "valid": True,
            "confidence": min(1.0, (0.20 - purple_border) / 0.15),
            "reason": None,
            "exact_card_identity_separate": True,
        }
    else:
        variant = {
            "value": None,
            "candidate": "special_variant_state",
            "valid": False,
            "confidence": max(purple_border, top_purple),
            "reason": "variant_visual_state_ambiguous",
            "exact_card_identity_separate": True,
        }
    return variant, ready_head, progress_head


def _semantics(crop: np.ndarray, identity_head: dict[str, Any]) -> dict[str, Any]:
    features = _visual_features(crop)
    variant, ready, progress = _variant_head(features, identity_head)
    return {
        "schema": SCHEMA,
        "variant_visual_state": variant,
        "evolution_ready": ready,
        "evolution_progress_diamonds": progress,
        "disabled_visual": _disabled_head(features),
        "printed_cost": copy.deepcopy(identity_head.get("displayed_cost", {})),
        "features": features,
        "current_frame_only": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--neutral", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--hero-evidence", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    rows = _rows(args.neutral.resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(args.video.resolve()),
        "-vf",
        "fps=10",
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    decoder = subprocess.Popen(command, stdout=subprocess.PIPE)
    assert decoder.stdout is not None
    frame_bytes = 1182 * 2560 * 3
    transient_rows = []
    counts: Counter[str] = Counter()
    for index, row in enumerate(rows):
        raw = decoder.stdout.read(frame_bytes)
        if len(raw) != frame_bytes:
            raise ValueError(f"short HUD decode at frame {index}")
        frame = np.frombuffer(raw, dtype=np.uint8).reshape(2560, 1182, 3)
        transient = {
            "schema": "clasher.youtube.offline_hud_transient_label.v1",
            "snapshot_id": row["snapshot_id"],
            "timestamp_ms": row["timestamp_ms"],
            "players": {},
            "offline_label_only": True,
            "actor_input": False,
        }
        for player_id in (0, 1):
            hud = row["offline_privileged_hud"][str(player_id)]
            layout = HUD_ROIS[player_id]
            heads = [*hud["hand"], hud["next_card"]]
            boxes = [*layout["hand"], layout["next"]]
            transients = []
            for slot, (head, box) in enumerate(zip(heads, boxes, strict=True)):
                crop = _crop_relative(frame, box)
                head["visual_semantics"] = _semantics(crop, head)
                semantic = head["visual_semantics"]
                variant_head = semantic["variant_visual_state"]
                if variant_head["valid"]:
                    counts[f"p{player_id}_variant_{variant_head['value']}"] += 1
                else:
                    counts[f"p{player_id}_variant_invalid"] += 1
                    counts[
                        f"p{player_id}_variant_candidate_{variant_head['candidate']}"
                    ] += 1
                counts[f"p{player_id}_disabled_valid"] += int(
                    semantic["disabled_visual"]["valid"]
                )
                candidate = head.get("candidate")
                disappearing = bool(candidate == "empty" or head.get("value") == "empty")
                transients.append(
                    {
                        "slot": "next" if slot == 4 else slot,
                        "selected_or_disappearing_candidate": disappearing,
                        "valid": disappearing,
                        "reason": None if disappearing else "selected_lift_head_not_calibrated",
                        "evidence": "current_frame_empty_slot_visual" if disappearing else None,
                    }
                )
            transient["players"][str(player_id)] = transients
        transient_rows.append(transient)
    decoder.stdout.close()
    if decoder.wait() != 0:
        raise ValueError("HUD semantics decode failed")

    neutral_path = args.output_dir / "neutral_sequence_hud_semantics.jsonl.gz"
    transient_path = args.output_dir / "offline_hud_transient_labels.jsonl.gz"
    _atomic_gzip_jsonl(neutral_path, rows)
    _atomic_gzip_jsonl(transient_path, transient_rows)
    identity_gold_path = args.output_dir / "offline_exact_hud_identity_gold.json"
    identity_gold: dict[str, Any] = {
        "schema": "clasher.youtube.offline_exact_hud_identity_gold.v1",
        "labels": [],
        "offline_label_only": True,
        "actor_input": False,
    }
    if args.hero_evidence is not None:
        evidence_path = args.hero_evidence.resolve()
        evidence = json.loads(evidence_path.read_text())
        decision = evidence["identity_decision"]
        if decision["status"] != "accepted_exact_identity_for_reviewed_test_sequence":
            raise ValueError("hero evidence is not an accepted reviewed sequence")
        stable_key = decision["stable_key"]
        identity_gold["authority"] = {
            "path": str(evidence_path),
            "sha256": _sha256(evidence_path),
        }
        identity_gold["labels"] = [
            {
                "snapshot_id": rows[308]["snapshot_id"],
                "timestamp_ms": 30_800,
                "player_id": 0,
                "slot": "next",
                "stable_key": stable_key,
                "evidence": "reviewed_next_to_hand_deployment_sequence",
            },
            {
                "snapshot_id": rows[314]["snapshot_id"],
                "timestamp_ms": 31_400,
                "player_id": 0,
                "slot": 1,
                "stable_key": stable_key,
                "evidence": "reviewed_next_to_hand_deployment_sequence",
            },
            {
                "snapshot_id": rows[371]["snapshot_id"],
                "timestamp_ms": 37_100,
                "player_id": 0,
                "slot": 1,
                "stable_key": stable_key,
                "evidence": "reviewed_pre_play_hand_anchor",
            },
            {
                "snapshot_id": rows[372]["snapshot_id"],
                "timestamp_ms": 37_200,
                "player_id": 0,
                "slot": 1,
                "stable_key": stable_key,
                "event": "played_and_disappeared",
                "evidence": "reviewed_elixir_drop_and_barblog_projectile",
            },
        ]
    _atomic_json(identity_gold_path, identity_gold)
    source_manifest_path = args.source_manifest.resolve()
    source_manifest = json.loads(source_manifest_path.read_text())
    source_manifest["parent_manifest"] = {
        "path": str(source_manifest_path),
        "sha256": _sha256(source_manifest_path),
    }
    source_manifest["artifacts"]["neutral_sequence"] = {
        "path": str(neutral_path.resolve()),
        "sha256": _sha256(neutral_path),
        "rows": len(rows),
    }
    source_manifest["hud_semantics"] = {
        "schema": SCHEMA,
        "current_frame_only_actor_fields": True,
        "exact_identity_separate_from_variant_state": True,
        "offline_transient_labels": {
            "path": str(transient_path.resolve()),
            "sha256": _sha256(transient_path),
            "rows": len(transient_rows),
            "actor_input": False,
        },
        "offline_exact_identity_gold": {
            "path": str(identity_gold_path.resolve()),
            "sha256": _sha256(identity_gold_path),
            "rows": len(identity_gold["labels"]),
            "actor_input": False,
        },
        "replay_disjoint_promotion_ready": False,
    }
    derived_manifest = args.output_dir / "source_manifest_hud_semantics.json"
    _atomic_json(derived_manifest, source_manifest)
    manifest = {
        "schema": SCHEMA,
        "video_sha256": _sha256(args.video),
        "neutral_input_sha256": _sha256(args.neutral),
        "neutral_output": {
            "path": str(neutral_path.resolve()),
            "sha256": _sha256(neutral_path),
            "rows": len(rows),
        },
        "offline_transient_labels": {
            "path": str(transient_path.resolve()),
            "sha256": _sha256(transient_path),
            "actor_input": False,
        },
        "offline_exact_identity_gold": {
            "path": str(identity_gold_path.resolve()),
            "sha256": _sha256(identity_gold_path),
            "rows": len(identity_gold["labels"]),
            "actor_input": False,
        },
        "derived_source_manifest": {
            "path": str(derived_manifest.resolve()),
            "sha256": _sha256(derived_manifest),
        },
        "counts": dict(sorted(counts.items())),
        "elapsed_seconds": time.perf_counter() - started,
        "promotion_gate": {
            "status": "blocked",
            "reasons": [
                "one-replay calibration is not replay-disjoint",
                "hero and evolution exact artwork identities are not proven",
                "selected-card lift state is not calibrated",
            ],
        },
    }
    manifest_path = args.output_dir / "manifest.json"
    _atomic_json(manifest_path, manifest)
    print(json.dumps({"manifest": str(manifest_path), "sha256": _sha256(manifest_path), "counts": manifest["counts"], "elapsed_seconds": manifest["elapsed_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
