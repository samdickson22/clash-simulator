from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import cv2
import numpy as np
import pyarrow.parquet as pq
import torch
from PIL import Image

from clasher.rl.tv_royale_replay import IMAGE_HEIGHT, IMAGE_WIDTH
from scripts.import_tv_royale_placements import (
    _combined_detections,
    _load_detector_models,
)
from scripts.render_tv_royale_extraction_audit import (
    _draw_detections,
    _draw_grid,
)

RAW_CROP_LEFT = 57
RAW_CROP_TOP = 137


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render raw-frame crop, grid, and detector visual audits."
    )
    parser.add_argument("--input-parquet", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--katacr-source-root", default="datasets/external/KataCR")
    parser.add_argument("--detector-weight", action="append", required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--samples", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--nms-iou", type=float, default=0.6)
    return parser.parse_args()


def _load_samples(path: Path, count: int) -> list[tuple[int, np.ndarray]]:
    parquet = pq.ParquetFile(path)
    total = parquet.metadata.num_rows
    indices = set(np.linspace(0, total - 1, min(count, total), dtype=np.int64))
    output = []
    source_index = 0
    for batch in parquet.iter_batches(
        columns=["frame_id", "image"], batch_size=128, use_threads=False
    ):
        for frame_id, encoded in zip(batch.column(0), batch.column(1), strict=True):
            if source_index in indices:
                raw = encoded.as_py()["bytes"]
                image = np.asarray(
                    Image.open(io.BytesIO(raw)).convert("RGB")
                )[..., ::-1].copy()
                output.append((int(frame_id.as_py()), image))
            source_index += 1
    return output


def _raw_panel(image: np.ndarray) -> np.ndarray:
    panel = image.copy()
    overlay = panel.copy()
    overlay[:] = (0, 0, 0)
    x1, y1 = RAW_CROP_LEFT, RAW_CROP_TOP
    x2, y2 = x1 + IMAGE_WIDTH, y1 + IMAGE_HEIGHT
    overlay[y1:y2, x1:x2] = panel[y1:y2, x1:x2]
    cv2.addWeighted(overlay, 0.60, panel, 0.40, 0.0, panel)
    cv2.rectangle(panel, (x1, y1), (x2, y2), (0, 255, 255), 3)
    cv2.putText(
        panel,
        "yellow = exact detector/grid crop",
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return cv2.resize(panel, (round(panel.shape[1] * IMAGE_HEIGHT / panel.shape[0]), IMAGE_HEIGHT))


def main() -> None:
    args = parse_args()
    if args.samples <= 0 or args.batch_size <= 0:
        raise ValueError("samples and batch size must be positive")
    source = Path(args.input_parquet).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = _load_samples(source, args.samples)
    models = _load_detector_models(
        [Path(value).resolve() for value in args.detector_weight],
        Path(args.katacr_source_root).resolve(),
    )
    manifest = []
    for start in range(0, len(samples), args.batch_size):
        chunk = samples[start : start + args.batch_size]
        crops = [
            image[
                RAW_CROP_TOP : RAW_CROP_TOP + IMAGE_HEIGHT,
                RAW_CROP_LEFT : RAW_CROP_LEFT + IMAGE_WIDTH,
            ].copy()
            for _, image in chunk
        ]
        per_model_results = [
            model.predict(
                crops,
                device=args.device,
                verbose=False,
                conf=args.confidence,
                iou=args.nms_iou,
                imgsz=(896, 576),
            )
            for model in models
        ]
        if args.device == "mps":
            torch.mps.synchronize()
        for index, ((frame_id, raw), crop) in enumerate(zip(chunk, crops, strict=True)):
            detections = _combined_detections(
                [results[index] for results in per_model_results],
                models,
                nms_iou=args.nms_iou,
            )
            grid = crop.copy()
            _draw_grid(grid)
            _draw_detections(grid, detections)
            raw_panel = _raw_panel(raw)
            header = np.zeros(
                (58, raw_panel.shape[1] + grid.shape[1], 3), dtype=np.uint8
            )
            cv2.putText(
                header,
                f"frame={frame_id} detections={len(detections)} raw={raw.shape[1]}x{raw.shape[0]} crop={IMAGE_WIDTH}x{IMAGE_HEIGHT}",
                (8, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                header,
                "left: UI exclusion  right: 18x32 grid; outlines are pixel detections, not hitboxes",
                (8, 48),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (210, 210, 210),
                1,
                cv2.LINE_AA,
            )
            canvas = np.concatenate((header, np.concatenate((raw_panel, grid), axis=1)), axis=0)
            output = output_dir / f"{start + index:04d}_frame_{frame_id:05d}.jpg"
            cv2.imwrite(str(output), canvas, [cv2.IMWRITE_JPEG_QUALITY, 94])
            manifest.append(
                {
                    "frame_id": frame_id,
                    "detections": len(detections),
                    "output": str(output),
                }
            )
    payload = {
        "source": str(source),
        "crop": [RAW_CROP_LEFT, RAW_CROP_TOP, IMAGE_WIDTH, IMAGE_HEIGHT],
        "samples": manifest,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
