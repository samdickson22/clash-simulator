from __future__ import annotations

# mypy: disable-error-code="import-not-found,import-untyped", follow-imports=skip
import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch

from scripts.extract_tv_royale_raw_cascade import _detect
from scripts.extract_tv_royale_youtube_fullmatch import ARENA_REGION
from scripts.import_tv_royale_placements import _load_detector_models


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark the exact dense two-detector YouTube full-match workload "
            "without running HUD, OCR, tracking, or serialization."
        )
    )
    parser.add_argument("--input-video", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--detector-weight", action="append", required=True)
    parser.add_argument("--katacr-root", default="datasets/external/KataCR")
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--output")
    return parser.parse_args()


def _read_exact(stream: Any, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _crop_relative(
    image: np.ndarray, box: tuple[float, float, float, float]
) -> np.ndarray:
    height, width = image.shape[:2]
    x, y, box_width, box_height = box
    x1 = max(0, min(width, round(x * width)))
    y1 = max(0, min(height, round(y * height)))
    x2 = max(x1 + 1, min(width, round((x + box_width) * width)))
    y2 = max(y1 + 1, min(height, round((y + box_height) * height)))
    return cast(np.ndarray, np.ascontiguousarray(image[y1:y2, x1:x2]))


def _run_repetition(
    *,
    source: Path,
    width: int,
    height: int,
    sample_hz: int,
    expected_frames: int,
    models: list[Any],
    device: str,
    batch_size: int,
) -> dict[str, Any]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        f"fps={sample_hz},scale={width}:{height}",
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    frame_bytes = width * height * 3
    detector_seconds = 0.0
    decoded_frames = 0
    detection_count = 0
    digest = hashlib.sha256()
    images: dict[int, np.ndarray] = {}

    def flush() -> None:
        nonlocal detector_seconds, detection_count
        if not images:
            return
        started = time.perf_counter()
        rows = _detect(
            models,
            images,
            device=device,
            batch_size=batch_size,
            confidence=0.4,
            nms_iou=0.6,
        )
        detector_seconds += time.perf_counter() - started
        for frame_index in sorted(rows):
            for row in rows[frame_index]:
                detection_count += 1
                digest.update(frame_index.to_bytes(4, "little"))
                digest.update(row.class_name.encode("utf-8"))
                belonging = -1 if row.belonging is None else int(row.belonging)
                digest.update(belonging.to_bytes(2, "little", signed=True))
                digest.update(
                    np.round(
                        [row.confidence, row.x1, row.y1, row.x2, row.y2], 4
                    ).astype(np.float32).tobytes()
                )
        images.clear()

    wall_started = time.perf_counter()
    while decoded_frames < expected_frames:
        raw = _read_exact(process.stdout, frame_bytes)
        if len(raw) != frame_bytes:
            break
        frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
        images[decoded_frames] = _crop_relative(frame, ARENA_REGION)
        decoded_frames += 1
        if len(images) == batch_size:
            flush()
    flush()
    stdout_tail, stderr = process.communicate()
    if stdout_tail:
        raise RuntimeError("ffmpeg emitted unexpected trailing raw bytes")
    if process.returncode != 0:
        raise RuntimeError(stderr.decode("utf-8", errors="replace"))
    if decoded_frames != expected_frames:
        raise RuntimeError(
            f"decoded {decoded_frames} frames, expected {expected_frames}"
        )
    return {
        "decoded_frames": decoded_frames,
        "detections": detection_count,
        "detection_digest": digest.hexdigest(),
        "detector_seconds": detector_seconds,
        "detector_frames_per_second": decoded_frames / detector_seconds,
        "wall_seconds": time.perf_counter() - wall_started,
    }


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0 or args.repetitions < 2:
        raise ValueError("batch-size must be positive and repetitions must be >= 2")
    source = Path(args.input_video).resolve()
    manifest_path = Path(args.source_manifest).resolve()
    acquisition = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_media = acquisition["source_media"]
    decode = acquisition["decode"]
    width = int(source_media["width"]) // 2
    height = int(source_media["height"]) // 2
    output_time_base = str(decode["output_time_base"])
    if not output_time_base.startswith("1/"):
        raise ValueError(f"unsupported output time base: {output_time_base}")
    sample_hz = int(output_time_base.removeprefix("1/"))
    expected_frames = int(decode["sample_count"])

    weights = [Path(value).resolve() for value in args.detector_weight]
    load_started = time.perf_counter()
    models = _load_detector_models(weights, Path(args.katacr_root).resolve())
    model_load_seconds = time.perf_counter() - load_started
    if args.device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    repetitions = [
        _run_repetition(
            source=source,
            width=width,
            height=height,
            sample_hz=sample_hz,
            expected_frames=expected_frames,
            models=models,
            device=args.device,
            batch_size=args.batch_size,
        )
        for _ in range(args.repetitions)
    ]
    stable = len({row["detection_digest"] for row in repetitions}) == 1
    payload = {
        "schema": "clasher.youtube.fullmatch.detector_benchmark.v1",
        "source": str(source),
        "source_manifest": str(manifest_path),
        "source_video_sha256": acquisition["source_media"]["sha256"],
        "frame_index_sha256": decode["index"]["sha256"],
        "sample_hz": sample_hz,
        "frames_per_repetition": expected_frames,
        "arena_region": list(ARENA_REGION),
        "semantic_scaled_frame": [width, height],
        "imgsz": [896, 576],
        "confidence": 0.4,
        "nms_iou": 0.6,
        "device": args.device,
        "batch_size": args.batch_size,
        "torch_version": torch.__version__,
        "model_load_seconds": model_load_seconds,
        "cuda_peak_allocated_bytes": (
            int(torch.cuda.max_memory_allocated()) if args.device == "cuda" else None
        ),
        "weights": [str(path) for path in weights],
        "repetitions": repetitions,
        "stable_repetition_digest": stable,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not stable:
        raise RuntimeError("repeated detector digests differ")
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
