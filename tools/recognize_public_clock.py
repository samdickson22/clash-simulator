#!/usr/bin/env -S uv run python
"""Portable current-frame Clash Royale spectator-clock recognizer.

The executable deliberately has no temporal state. Every published anchor is
decoded from that anchor's frame alone; ambiguous transitions are omitted.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import tempfile
import zlib
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

ANCHOR_SCHEMA = "clasher.youtube.clock_anchor.v1"
CLOCK_REGION = (0.805, 0.165, 0.195, 0.075)
CANONICAL_CLOCK_SIZE = (230, 192)
SUPPORTED_SOURCE_SIZES = frozenset({(1182, 2560), (886, 1920)})
PATCH_SIZE = (32, 40)
# Frozen from the minimum confidence among all 535 exact teacher-aligned anchors
# on the original 1182x2560 calibration source. Predictions below the observed
# clean-calibration support fail closed; the replay-disjoint canary was not used
# to select this boundary.
CONFIDENCE_THRESHOLD = 0.5560975423673304
TEMPLATES_ZLIB_BASE64 = (
    "eNrtmtsagzAIg3n/l85ud6glELDV2Tv3T/16MARas+s0vLcJ+v0D5hzjpnJ4HD/"
    "469pi1zbkqOYm8s8f8D8cznS7y2O8vqCuX0twe9pEpjwBi6lbBcdi7vb/4Q9/"
    "uMR3cmjmGTTPf7n+jOZZexblzhCwkyjy+fM9kVZEfm4R0Icdd4Lgs0Pdqg3c6p"
    "Qx08Lax6vwrbSPyFypGXJnUJXPOnll1yGzlo3nYggN3y1+xuroIahS/ROwgMdG"
    "gPwCkuFfzK7z8enemfOkg1DsR/wDivG4hKcKmAcK9vbbdIU5/EAhUcQPFBhzjhD"
    "n7cOgPtfBrY23pA/L+Q0ELBqexQiDrXi5ZzvRcRCmg9p7YnaXSvMfRh8Y/fD1Z"
    "SFP7/Dlvi86/woGd8GUX1gArcT+pFY/enldfailKlwrj3TwYvzXbpzarjWPm8jR"
    "xlPjo8enXPiKF5d2UL2V+w+reGEx+7zbbentt+sczhub3iBnS9/uJc23yJApCd"
    "UzrPPz64Ol1HwcL1Yfs5r8JlbdTOXQ8vz5DnQ4oHDO94EvODLce3+AJ88HyvE/"
    "4+/+qfin5rfWon9n+VM4AuTkL+r16vxpdx6tRTXXK4QDSLUFvr4CIOJl1zbVfA"
    "H+Elfs"
)


def _load_templates() -> dict[int, np.ndarray]:
    raw = zlib.decompress(base64.b64decode(TEMPLATES_ZLIB_BASE64))
    expected = 10 * PATCH_SIZE[0] * PATCH_SIZE[1]
    if len(raw) != expected:
        raise RuntimeError("embedded clock template length mismatch")
    array = np.frombuffer(raw, dtype=np.uint8).reshape(10, PATCH_SIZE[1], PATCH_SIZE[0])
    return {digit: array[digit] for digit in range(10)}


TEMPLATES = _load_templates()


def _clock_crop(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    x, y, box_width, box_height = CLOCK_REGION
    x1, y1 = round(x * width), round(y * height)
    x2, y2 = round((x + box_width) * width), round((y + box_height) * height)
    crop = frame[y1:y2, x1:x2]
    if (crop.shape[1], crop.shape[0]) == CANONICAL_CLOCK_SIZE:
        return crop
    return cv2.resize(crop, CANONICAL_CLOCK_SIZE, interpolation=cv2.INTER_CUBIC)


def _digit_mask(crop: np.ndarray) -> np.ndarray:
    b, g, r = cv2.split(crop)
    mask = ((b > 175) & (g > 175) & (r > 175)).astype(np.uint8) * 255
    output = np.zeros_like(mask)
    output[57:119, 38:207] = mask[57:119, 38:207]
    return cv2.morphologyEx(output, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))


def _components(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    candidates: list[tuple[int, int, int, int]] = []
    for x, y, width, height, area in stats[1:]:
        if y < 57 or y > 82 or height < 25 or width < 8 or area < 120:
            continue
        candidates.append((int(x), int(y), int(width), int(height)))
    candidates.sort()
    return candidates if len(candidates) == 3 else []


def _normalized_patch(mask: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x, y, width, height = box
    digit = mask[y : y + height, x : x + width]
    target_width, target_height = PATCH_SIZE
    scale = min((target_width - 4) / width, (target_height - 4) / height)
    resized = cv2.resize(
        digit,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_NEAREST,
    )
    output = np.zeros((target_height, target_width), dtype=np.uint8)
    y1 = (target_height - resized.shape[0]) // 2
    x1 = (target_width - resized.shape[1]) // 2
    output[y1 : y1 + resized.shape[0], x1 : x1 + resized.shape[1]] = resized
    return output


def recognize_current_frame(frame: np.ndarray) -> tuple[int, float] | None:
    """Return seconds/confidence or fail closed for one independent frame."""
    mask = _digit_mask(_clock_crop(frame))
    boxes = _components(mask)
    if len(boxes) != 3:
        return None
    predictions: list[int] = []
    confidence = 1.0
    for box in boxes:
        patch = _normalized_patch(mask, box).astype(np.float32) / 255.0
        ranked: list[tuple[float, int]] = []
        for digit, template in TEMPLATES.items():
            distance = float(np.mean((patch - template.astype(np.float32) / 255.0) ** 2))
            ranked.append((distance, digit))
        ranked.sort()
        best_distance, best_digit = ranked[0]
        second_distance = ranked[1][0]
        digit_confidence = max(
            0.0,
            min(1.0, (second_distance - best_distance) / max(second_distance, 1e-8)),
        )
        if digit_confidence < CONFIDENCE_THRESHOLD:
            return None
        predictions.append(best_digit)
        confidence = min(confidence, digit_confidence)
    if predictions[1] > 5:
        return None
    seconds = predictions[0] * 60 + predictions[1] * 10 + predictions[2]
    if seconds > 599:
        return None
    return seconds, confidence


def _decode_frames(
    source_video: Path, *, sample_hz: int, width: int, height: int
) -> Iterator[tuple[int, np.ndarray]]:
    command = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-i",
        str(source_video),
        "-vf",
        f"fps={sample_hz}",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    frame_bytes = width * height * 3
    output_pts = 0
    while True:
        data = process.stdout.read(frame_bytes)
        if not data:
            break
        if len(data) != frame_bytes:
            process.kill()
            raise RuntimeError("truncated ffmpeg frame")
        yield output_pts, np.frombuffer(data, np.uint8).reshape(height, width, 3)
        output_pts += 1
    process.stdout.close()
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    if process.wait() != 0:
        raise RuntimeError(f"ffmpeg decode failed: {stderr[-2000:]}")


def _atomic_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            for row in rows:
                output.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
                output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-video", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--sample-hz", type=int, required=True)
    parser.add_argument("--anchor-stride-frames", type=int, required=True)
    args = parser.parse_args()
    if args.sample_hz != 10:
        raise ValueError("portable clock v1 is calibrated only for exact 10 Hz decode")
    if args.anchor_stride_frames <= 0:
        raise ValueError("anchor stride must be positive")
    manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    media = manifest.get("source_media", {})
    width, height = int(media["width"]), int(media["height"])
    if (width, height) not in SUPPORTED_SOURCE_SIZES:
        raise ValueError(
            f"portable clock source size is unsupported: {width}x{height}"
        )
    rows: list[dict[str, object]] = []
    for output_pts, frame in _decode_frames(
        args.source_video,
        sample_hz=args.sample_hz,
        width=width,
        height=height,
    ):
        if output_pts % args.anchor_stride_frames:
            continue
        result = recognize_current_frame(frame)
        if result is None:
            continue
        seconds, confidence = result
        rows.append(
            {
                "schema": ANCHOR_SCHEMA,
                "output_pts": output_pts,
                "seconds_remaining": seconds,
                "confidence": confidence,
                "raw_text": [f"portable_template:{seconds // 60}:{seconds % 60:02d}"],
                "current_frame_only": True,
            }
        )
    if not rows:
        raise RuntimeError("portable clock produced no confident anchors")
    _atomic_jsonl(args.output_jsonl, rows)


if __name__ == "__main__":
    main()
