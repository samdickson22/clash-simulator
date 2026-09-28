from __future__ import annotations

import argparse
import gc
import hashlib
import io
import json
import resource
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import torch
from PIL import Image

from scripts.import_tv_royale_placements import _load_detector_models


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark the pinned two-model KataCR vision pipeline."
    )
    parser.add_argument("--input-parquet", required=True)
    parser.add_argument("--katacr-source-root", default="datasets/external/KataCR")
    parser.add_argument("--detector-weight", action="append", required=True)
    parser.add_argument("--device", action="append", choices=("cpu", "mps", "cuda"))
    parser.add_argument("--batch-size", action="append", type=int)
    parser.add_argument("--frames", type=int, default=128)
    parser.add_argument("--warmup-frames", type=int, default=16)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--parquet-batch-size", type=int, default=128)
    parser.add_argument("--sample-mode", choices=("head", "even"), default="even")
    parser.add_argument(
        "--crop",
        nargs=4,
        type=int,
        metavar=("LEFT", "TOP", "WIDTH", "HEIGHT"),
        help="crop each decoded source frame before detector inference",
    )
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--nms-iou", type=float, default=0.6)
    parser.add_argument("--imgsz-height", type=int, default=896)
    parser.add_argument("--imgsz-width", type=int, default=576)
    parser.add_argument("--torch-threads", type=int, default=10)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def _sync(device: str) -> None:
    if device == "mps":
        torch.mps.synchronize()
    elif device == "cuda":
        torch.cuda.synchronize()


def _load_encoded_frames(
    path: Path, *, count: int, parquet_batch_size: int, sample_mode: str
) -> list[bytes]:
    parquet = pq.ParquetFile(path)
    total_rows = parquet.metadata.num_rows
    if count > total_rows:
        raise ValueError(f"requested {count} images from a {total_rows}-row source")
    if sample_mode == "even":
        selected = set(np.linspace(0, total_rows - 1, count, dtype=np.int64).tolist())
    else:
        selected = set(range(count))
    encoded: list[bytes] = []
    image_column = "png_bytes" if "png_bytes" in parquet.schema_arrow.names else "image"
    source_index = 0
    for batch in parquet.iter_batches(
        columns=[image_column], batch_size=parquet_batch_size, use_threads=False
    ):
        for value in batch.column(0):
            if source_index in selected:
                raw = value.as_py()
                if isinstance(raw, dict):
                    raw = raw.get("bytes")
                if raw:
                    encoded.append(bytes(raw))
            source_index += 1
            if len(encoded) >= count:
                return encoded
    return encoded


def _decode(
    encoded: list[bytes], crop: tuple[int, int, int, int] | None
) -> list[np.ndarray]:
    output = []
    for raw in encoded:
        image = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"))[..., ::-1]
        if crop is not None:
            left, top, width, height = crop
            image = image[top : top + height, left : left + width]
        output.append(image.copy())
    return output


def _predict(
    models: list[Any],
    images: list[np.ndarray],
    *,
    device: str,
    batch_size: int,
    confidence: float,
    nms_iou: float,
    imgsz: tuple[int, int],
) -> tuple[int, str]:
    detections = 0
    digest = hashlib.sha256()
    for start in range(0, len(images), batch_size):
        chunk = images[start : start + batch_size]
        for model_index, model in enumerate(models):
            results = model.predict(
                chunk,
                device=device,
                verbose=False,
                conf=confidence,
                iou=nms_iou,
                imgsz=imgsz,
            )
            for frame_index, result in enumerate(results):
                rows = result.orig_boxes.detach().cpu().numpy()
                detections += int(rows.shape[0])
                digest.update(model_index.to_bytes(1, "little"))
                digest.update((start + frame_index).to_bytes(4, "little"))
                digest.update(np.round(rows, 4).astype(np.float32).tobytes())
    _sync(device)
    return detections, digest.hexdigest()


def main() -> None:
    args = parse_args()
    if args.frames <= 0 or args.warmup_frames <= 0 or args.repetitions < 2:
        raise ValueError("frames/warmup must be positive and repetitions must be >= 2")
    devices = args.device or (["mps", "cpu"] if torch.backends.mps.is_available() else ["cpu"])
    batch_sizes = args.batch_size or [1, 4, 8, 16, 32]
    if any(value <= 0 for value in batch_sizes):
        raise ValueError("batch sizes must be positive")
    torch.set_num_threads(args.torch_threads)

    source = Path(args.input_parquet).resolve()
    crop = tuple(args.crop) if args.crop is not None else None
    if crop is not None and any(value < 0 for value in crop):
        raise ValueError("crop values must be non-negative")
    encoded_start = time.perf_counter()
    encoded = _load_encoded_frames(
        source,
        count=max(args.frames, args.warmup_frames),
        parquet_batch_size=args.parquet_batch_size,
        sample_mode=args.sample_mode,
    )
    encoded_seconds = time.perf_counter() - encoded_start
    if len(encoded) < max(args.frames, args.warmup_frames):
        raise ValueError(f"source has only {len(encoded)} usable images")

    decode_times = []
    decoded: list[np.ndarray] = []
    for _ in range(args.repetitions):
        start = time.perf_counter()
        candidate = _decode(encoded[: args.frames], crop)
        decode_times.append(time.perf_counter() - start)
        decoded = candidate

    load_start = time.perf_counter()
    models = _load_detector_models(
        [Path(value).resolve() for value in args.detector_weight],
        Path(args.katacr_source_root).resolve(),
    )
    model_load_seconds = time.perf_counter() - load_start
    parameter_counts = [sum(parameter.numel() for parameter in model.model.parameters()) for model in models]

    rows: list[dict[str, Any]] = []
    for device in devices:
        for batch_size in batch_sizes:
            _predict(
                models,
                decoded[: args.warmup_frames],
                device=device,
                batch_size=batch_size,
                confidence=args.confidence,
                nms_iou=args.nms_iou,
                imgsz=(args.imgsz_height, args.imgsz_width),
            )
            durations: list[float] = []
            hashes: list[str] = []
            detection_counts: list[int] = []
            for _ in range(args.repetitions):
                gc.collect()
                start = time.perf_counter()
                count, digest = _predict(
                    models,
                    decoded[: args.frames],
                    device=device,
                    batch_size=batch_size,
                    confidence=args.confidence,
                    nms_iou=args.nms_iou,
                    imgsz=(args.imgsz_height, args.imgsz_width),
                )
                durations.append(time.perf_counter() - start)
                hashes.append(digest)
                detection_counts.append(count)
            median_seconds = statistics.median(durations)
            row = {
                "device": device,
                "batch_size": batch_size,
                "frames": args.frames,
                "models": len(models),
                "durations_seconds": durations,
                "median_seconds": median_seconds,
                "frames_per_second": args.frames / median_seconds,
                "model_frame_inferences_per_second": (
                    args.frames * len(models) / median_seconds
                ),
                "detection_counts": detection_counts,
                "detection_hashes": hashes,
                "stable_detection_hash": len(set(hashes)) == 1,
            }
            rows.append(row)
            print(json.dumps(row, sort_keys=True), flush=True)

    payload = {
        "source": str(source),
        "encoded_frames": len(encoded),
        "encoded_read_seconds": encoded_seconds,
        "sample_mode": args.sample_mode,
        "crop": list(crop) if crop is not None else None,
        "decode_seconds": decode_times,
        "decode_median_seconds": statistics.median(decode_times),
        "decode_frames_per_second": args.frames / statistics.median(decode_times),
        "model_load_seconds": model_load_seconds,
        "model_parameter_counts": parameter_counts,
        "total_parameters": sum(parameter_counts),
        "torch_version": torch.__version__,
        "torch_threads": args.torch_threads,
        "mps_available": torch.backends.mps.is_available(),
        "max_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "confidence": args.confidence,
        "nms_iou": args.nms_iou,
        "imgsz": [args.imgsz_height, args.imgsz_width],
        "results": rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
