from __future__ import annotations

import argparse
import base64
import gzip
import json
import subprocess
import time
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import cv2
import numpy as np

CLOCK_REGION = (0.805, 0.165, 0.195, 0.075)
PATCH_SIZE = (32, 40)
HOLDOUT_BLOCKS_MS = (
    (30_000, 45_000),
    (90_000, 105_000),
    (150_000, 165_000),
    (210_000, 225_000),
    (270_000, 285_000),
)


@dataclass(frozen=True)
class Teacher:
    output_pts: int
    timestamp_ms: int
    seconds: int


def _in_holdout(timestamp_ms: int) -> bool:
    return any(start <= timestamp_ms < end for start, end in HOLDOUT_BLOCKS_MS)


def _teacher_rows(path: Path) -> dict[int, Teacher]:
    result: dict[int, Teacher] = {}
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            output_pts = int(row["output_pts"])
            if output_pts % 5:
                continue
            clock = row["public"]["clock"]
            if not clock.get("valid") or int(clock["anchor_output_pts"]) != output_pts:
                continue
            result[output_pts] = Teacher(
                output_pts=output_pts,
                timestamp_ms=int(row["timestamp_ms"]),
                seconds=int(clock["value"]),
            )
    return result


def _clock_crop(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    x, y, box_width, box_height = CLOCK_REGION
    x1, y1 = round(x * width), round(y * height)
    x2, y2 = round((x + box_width) * width), round((y + box_height) * height)
    return frame[y1:y2, x1:x2]


def _digit_mask(crop: np.ndarray) -> np.ndarray:
    b, g, r = cv2.split(crop)
    white = (b > 175) & (g > 175) & (r > 175)
    mask = (white.astype(np.uint8) * 255)
    # The digit baseline is stable; this removes title and arena/background pixels.
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
    if len(candidates) != 3:
        return []
    return candidates


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


def _decode_frames(
    video: Path, expected_width: int, expected_height: int
) -> Iterator[tuple[int, np.ndarray]]:
    command = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-vf",
        "fps=10",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    frame_bytes = expected_width * expected_height * 3
    output_pts = 0
    while True:
        data = process.stdout.read(frame_bytes)
        if not data:
            break
        if len(data) != frame_bytes:
            raise RuntimeError("truncated ffmpeg frame")
        yield output_pts, np.frombuffer(data, np.uint8).reshape(
            expected_height, expected_width, 3
        )
        output_pts += 1
    process.stdout.close()
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    if process.wait() != 0:
        raise RuntimeError(stderr[-2000:])


def _labels(seconds: int) -> tuple[int, int, int]:
    minutes, remainder = divmod(seconds, 60)
    return minutes, remainder // 10, remainder % 10


def _fit(samples: list[tuple[Teacher, list[np.ndarray]]]) -> dict[int, np.ndarray]:
    buckets: dict[int, list[np.ndarray]] = {digit: [] for digit in range(10)}
    for teacher, patches in samples:
        for digit, patch in zip(_labels(teacher.seconds), patches, strict=True):
            buckets[digit].append(patch.astype(np.float32) / 255.0)
    missing = [digit for digit, values in buckets.items() if not values]
    if missing:
        raise RuntimeError(f"calibration is missing digits: {missing}")
    return {
        digit: np.asarray(np.mean(values, axis=0) >= 0.5, dtype=np.uint8) * 255
        for digit, values in buckets.items()
    }


def _distance(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.mean((left.astype(np.float32) / 255 - right.astype(np.float32) / 255) ** 2))


def _predict(
    patches: list[np.ndarray], templates: dict[int, np.ndarray], threshold: float
) -> tuple[int | None, float, list[dict[str, float | int]]]:
    predictions: list[int] = []
    evidence: list[dict[str, float | int]] = []
    confidence = 1.0
    for patch in patches:
        ranked = sorted((_distance(patch, template), digit) for digit, template in templates.items())
        best_distance, best_digit = ranked[0]
        second_distance = ranked[1][0]
        margin = second_distance - best_distance
        digit_confidence = max(0.0, min(1.0, margin / max(second_distance, 1e-8)))
        evidence.append(
            {
                "digit": best_digit,
                "distance": best_distance,
                "margin": margin,
                "confidence": digit_confidence,
            }
        )
        if digit_confidence < threshold:
            return None, 0.0, evidence
        predictions.append(best_digit)
        confidence = min(confidence, digit_confidence)
    seconds = predictions[0] * 60 + predictions[1] * 10 + predictions[2]
    if predictions[1] > 5 or seconds > 599:
        return None, 0.0, evidence
    return seconds, confidence, evidence


def _serialize_templates(templates: dict[int, np.ndarray]) -> str:
    packed = np.stack([templates[digit] for digit in range(10)]).tobytes()
    return base64.b64encode(zlib.compress(packed, level=9)).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-video", type=Path, required=True)
    parser.add_argument("--teacher-neutral", type=Path, required=True)
    parser.add_argument("--source-width", type=int, default=1182)
    parser.add_argument("--source-height", type=int, default=2560)
    parser.add_argument("--confidence-threshold", type=float, default=0.12)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    teachers = _teacher_rows(args.teacher_neutral)
    calibration: list[tuple[Teacher, list[np.ndarray]]] = []
    holdout: list[tuple[Teacher, list[np.ndarray]]] = []
    segmentation_failures: list[int] = []
    started = time.perf_counter()
    for output_pts, frame in _decode_frames(
        args.source_video, args.source_width, args.source_height
    ):
        teacher = teachers.get(output_pts)
        if teacher is None:
            continue
        mask = _digit_mask(_clock_crop(frame))
        boxes = _components(mask)
        if len(boxes) != 3:
            segmentation_failures.append(output_pts)
            continue
        patches = [_normalized_patch(mask, box) for box in boxes]
        (holdout if _in_holdout(teacher.timestamp_ms) else calibration).append(
            (teacher, patches)
        )
    decode_wall = time.perf_counter() - started
    templates = _fit(calibration)

    def evaluate(rows: list[tuple[Teacher, list[np.ndarray]]]) -> dict[str, Any]:
        accepted = 0
        correct = 0
        exact_errors: list[dict[str, Any]] = []
        accepted_sequence: list[tuple[int, int]] = []
        inference_started = time.perf_counter()
        for teacher, patches in rows:
            prediction, confidence, evidence = _predict(
                patches, templates, args.confidence_threshold
            )
            if prediction is None:
                continue
            accepted += 1
            accepted_sequence.append((teacher.timestamp_ms, prediction))
            if prediction == teacher.seconds:
                correct += 1
            else:
                exact_errors.append(
                    {
                        "output_pts": teacher.output_pts,
                        "timestamp_ms": teacher.timestamp_ms,
                        "teacher": teacher.seconds,
                        "prediction": prediction,
                        "confidence": confidence,
                        "digits": evidence,
                    }
                )
        inference_wall = time.perf_counter() - inference_started
        monotonic_violations = 0
        for (prior_ms, prior), (current_ms, current) in pairwise(accepted_sequence):
            elapsed = (current_ms - prior_ms) / 1000
            # Regulation -> overtime is the only legal upward discontinuity.
            if current > prior and not (prior <= 1 and 115 <= current <= 120):
                monotonic_violations += 1
            if current < max(0, prior - int(elapsed) - 2):
                monotonic_violations += 1
        return {
            "teacher_rows": len(rows),
            "accepted": accepted,
            "coverage": accepted / len(rows) if rows else 0.0,
            "correct": correct,
            "conditional_accuracy": correct / accepted if accepted else 0.0,
            "unconditional_accuracy": correct / len(rows) if rows else 0.0,
            "errors": exact_errors,
            "monotonic_violations": monotonic_violations,
            "inference_wall_seconds": inference_wall,
            "latency_ms_per_anchor": 1000 * inference_wall / len(rows) if rows else 0.0,
        }

    result = {
        "schema": "clasher.youtube.portable_clock_build.v1",
        "source_video": str(args.source_video.resolve()),
        "teacher_neutral": str(args.teacher_neutral.resolve()),
        "split": {
            "calibration_blocks": "all teacher anchors outside holdout_blocks_ms",
            "holdout_blocks_ms": HOLDOUT_BLOCKS_MS,
        },
        "confidence_threshold": args.confidence_threshold,
        "template_shape": [10, PATCH_SIZE[1], PATCH_SIZE[0]],
        "templates_zlib_base64": _serialize_templates(templates),
        "segmentation_failures": segmentation_failures,
        "decode_wall_seconds": decode_wall,
        "calibration": evaluate(calibration),
        "holdout": evaluate(holdout),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
