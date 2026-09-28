from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from scripts.extract_tv_royale_youtube_fullmatch import (
    HUD_ROIS,
    _atomic_json,
    _crop_relative,
    _sha256,
)


def _features(crop: np.ndarray) -> dict[str, float]:
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gold = (
        (hsv[:, :, 0] >= 8)
        & (hsv[:, :, 0] <= 38)
        & (hsv[:, :, 1] >= 100)
        & (hsv[:, :, 2] >= 100)
    )
    purple = (
        (hsv[:, :, 0] >= 125)
        & (hsv[:, :, 0] <= 170)
        & (hsv[:, :, 1] >= 90)
        & (hsv[:, :, 2] >= 80)
    )
    grayscale = hsv[:, :, 1] <= 42
    height, width = crop.shape[:2]
    border = np.zeros((height, width), dtype=np.bool_)
    border_width = max(2, round(min(height, width) * 0.10))
    border[:border_width] = True
    border[-border_width:] = True
    border[:, :border_width] = True
    border[:, -border_width:] = True
    top = purple[: max(1, round(height * 0.22))].astype(np.uint8) * 255
    components, _, stats, _ = cv2.connectedComponentsWithStats(top)
    diamond_components = sum(
        1
        for component in range(1, components)
        if 8 <= int(stats[component, cv2.CC_STAT_AREA]) <= height * width * 0.05
    )
    return {
        "gold_fraction": float(np.mean(gold)),
        "purple_fraction": float(np.mean(purple)),
        "grayscale_fraction": float(np.mean(grayscale)),
        "mean_saturation": float(np.mean(hsv[:, :, 1]) / 255.0),
        "mean_value": float(np.mean(hsv[:, :, 2]) / 255.0),
        "gold_border_fraction": float(np.mean(gold[border])),
        "purple_border_fraction": float(np.mean(purple[border])),
        "top_purple_components": float(diamond_components),
    }


def _cell(
    crop: np.ndarray,
    *,
    player_id: int,
    slot: str,
    timestamp_ms: int,
    features: dict[str, float],
) -> np.ndarray:
    image = cv2.resize(crop, (180, 220), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((280, 180, 3), dtype=np.uint8)
    canvas[:220] = image
    lines = [
        f"{timestamp_ms / 1000:.1f}s p{player_id} {slot}",
        f"gold {features['gold_fraction']:.3f} purple {features['purple_fraction']:.3f}",
        f"gray {features['grayscale_fraction']:.3f} sat {features['mean_saturation']:.3f}",
    ]
    for index, line in enumerate(lines):
        cv2.putText(
            canvas,
            line,
            (3, 238 + index * 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--timestamps-ms",
        type=int,
        nargs="+",
        default=[
            25_800,
            30_800,
            31_400,
            37_100,
            37_200,
            37_400,
            76_800,
            109_200,
            148_400,
            181_900,
            215_000,
            246_400,
        ],
    )
    args = parser.parse_args()
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
    decoder = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    assert decoder.stdout is not None
    selected = set(args.timestamps_ms)
    maximum_index = max(args.timestamps_ms) // 100
    records: list[dict[str, Any]] = []
    cells: list[np.ndarray] = []
    frame_bytes = 1182 * 2560 * 3
    for index in range(maximum_index + 1):
        raw = decoder.stdout.read(frame_bytes)
        if len(raw) != frame_bytes:
            raise ValueError(f"short exact atlas decode at frame {index}")
        timestamp_ms = index * 100
        if timestamp_ms not in selected:
            continue
        frame = np.frombuffer(raw, dtype=np.uint8).reshape(2560, 1182, 3)
        for player_id in (0, 1):
            layout = HUD_ROIS[player_id]
            boxes = [*layout["hand"], layout["next"]]
            for slot_index, box in enumerate(boxes):
                slot = "next" if slot_index == 4 else f"hand{slot_index}"
                crop = _crop_relative(frame, box)
                features = _features(crop)
                path = args.output_dir / f"t{timestamp_ms:06d}_p{player_id}_{slot}.png"
                if not cv2.imwrite(str(path), crop):
                    raise ValueError(f"could not write {path}")
                records.append(
                    {
                        "timestamp_ms": timestamp_ms,
                        "player_id": player_id,
                        "slot": slot,
                        "path": str(path),
                        "sha256": _sha256(path),
                        "features": features,
                    }
                )
                cells.append(
                    _cell(
                        crop,
                        player_id=player_id,
                        slot=slot,
                        timestamp_ms=timestamp_ms,
                        features=features,
                    )
                )
    decoder.stdout.close()
    decoder.terminate()
    decoder.wait()
    columns = 5
    rows = [
        np.hstack(cells[start : start + columns])
        for start in range(0, len(cells), columns)
    ]
    contact = np.vstack(rows)
    contact_path = args.output_dir / "hud_semantics_atlas.jpg"
    if not cv2.imwrite(str(contact_path), contact, [cv2.IMWRITE_JPEG_QUALITY, 94]):
        raise ValueError("could not write contact")
    manifest = {
        "schema": "clasher.youtube.hud_semantics_atlas.v1",
        "video_sha256": _sha256(args.video),
        "timestamps_ms": args.timestamps_ms,
        "records": records,
        "contact": {
            "path": str(contact_path),
            "sha256": _sha256(contact_path),
            "cells": len(cells),
        },
    }
    manifest_path = args.output_dir / "manifest.json"
    _atomic_json(manifest_path, manifest)
    print(json.dumps({"manifest": str(manifest_path), "sha256": _sha256(manifest_path), "contact": manifest["contact"]}, indent=2))


if __name__ == "__main__":
    main()
