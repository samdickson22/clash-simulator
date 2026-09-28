from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pyarrow.parquet as pq
import torch
from PIL import Image

from clasher.arena import TileGrid
from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH
from clasher.rl.tv_royale_replay import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    Y_OFFSET_BOTTOM,
    Y_OFFSET_TOP,
    TVRoyaleDetection,
    TVRoyalePlacementConverter,
    recover_deployment_clock,
)
from scripts.import_tv_royale_clock_placements import PairKey, _candidate_pairs
from scripts.import_tv_royale_placements import (
    _combined_detections,
    _load_detector_models,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render grid-registered visual audits for TV Royale extraction."
    )
    parser.add_argument("--input-parquet", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--katacr-source-root", default="datasets/external/KataCR")
    parser.add_argument("--detector-weight", action="append", required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--parquet-batch-size", type=int, default=64)
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--nms-iou", type=float, default=0.6)
    parser.add_argument("--clock-confidence", type=float, default=0.75)
    parser.add_argument("--existing-clock-distance", type=float, default=24.0)
    parser.add_argument("--clock-cluster-distance", type=float, default=18.0)
    return parser.parse_args()


def _source_tile_bounds(canonical_tile: int) -> tuple[int, int, int, int]:
    canonical_x = canonical_tile % BOARD_WIDTH
    canonical_y = canonical_tile // BOARD_WIDTH
    source_x = BOARD_WIDTH - 1 - canonical_x
    source_y = BOARD_HEIGHT - 1 - canonical_y
    grid_height = IMAGE_HEIGHT - Y_OFFSET_TOP - Y_OFFSET_BOTTOM
    x1 = round(source_x * IMAGE_WIDTH / BOARD_WIDTH)
    x2 = round((source_x + 1) * IMAGE_WIDTH / BOARD_WIDTH)
    y1 = round(Y_OFFSET_TOP + source_y * grid_height / BOARD_HEIGHT)
    y2 = round(Y_OFFSET_TOP + (source_y + 1) * grid_height / BOARD_HEIGHT)
    return x1, y1, x2, y2


def _draw_grid(image: np.ndarray) -> None:
    grid_height = IMAGE_HEIGHT - Y_OFFSET_TOP - Y_OFFSET_BOTTOM
    overlay = image.copy()
    overlay[:Y_OFFSET_TOP] = (0, 0, 0)
    overlay[IMAGE_HEIGHT - Y_OFFSET_BOTTOM :] = (0, 0, 0)
    cv2.addWeighted(overlay, 0.30, image, 0.70, 0.0, image)
    for x in range(BOARD_WIDTH + 1):
        pixel = round(x * IMAGE_WIDTH / BOARD_WIDTH)
        cv2.line(image, (pixel, Y_OFFSET_TOP), (pixel, IMAGE_HEIGHT - Y_OFFSET_BOTTOM), (155, 155, 155), 1)
    for y in range(BOARD_HEIGHT + 1):
        pixel = round(Y_OFFSET_TOP + y * grid_height / BOARD_HEIGHT)
        color = (0, 255, 255) if y == BOARD_HEIGHT // 2 else (155, 155, 155)
        thickness = 2 if y == BOARD_HEIGHT // 2 else 1
        cv2.line(image, (0, pixel), (IMAGE_WIDTH, pixel), color, thickness)
    for canonical_x, canonical_y in TileGrid.BLOCKED_TILES:
        tile = canonical_y * BOARD_WIDTH + canonical_x
        x1, y1, x2, y2 = _source_tile_bounds(tile)
        cv2.rectangle(image, (x1, y1), (x2, y2), (70, 70, 70), -1)


def _draw_detections(image: np.ndarray, detections: list[TVRoyaleDetection]) -> None:
    for detection in detections:
        color = (255, 110, 30) if detection.belonging == 0 else (40, 70, 255)
        x1, y1, x2, y2 = map(
            round, (detection.x1, detection.y1, detection.x2, detection.y2)
        )
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 1)
        cv2.circle(image, (round((x1 + x2) / 2), round((y1 + y2) / 2)), 3, color, -1)
        label = f"{detection.class_name} {detection.confidence:.2f}"
        cv2.putText(
            image,
            label,
            (x1, max(12, y1 - 3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.32,
            color,
            1,
            cv2.LINE_AA,
        )


def _draw_location(
    image: np.ndarray,
    *,
    x: int,
    y: int,
    tile: int,
    color: tuple[int, int, int],
    label: str,
) -> None:
    x1, y1, x2, y2 = _source_tile_bounds(tile)
    overlay = image.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    cv2.addWeighted(overlay, 0.28, image, 0.72, 0.0, image)
    cv2.drawMarker(image, (x, y), color, cv2.MARKER_CROSS, 22, 3)
    cv2.putText(
        image,
        f"{label} t={tile}",
        (max(2, min(x + 8, IMAGE_WIDTH - 110)), max(14, y - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        color,
        2,
        cv2.LINE_AA,
    )


def _select_candidates(
    candidates: list[tuple[PairKey, int, int]], samples: int
) -> list[tuple[PairKey, int, int]]:
    if len(candidates) <= samples:
        return candidates
    indices = np.linspace(0, len(candidates) - 1, samples, dtype=np.int64)
    return [candidates[int(index)] for index in indices]


def _load_rows(
    path: Path,
    selected: list[tuple[PairKey, int, int]],
    *,
    batch_size: int,
) -> dict[PairKey, dict[str, Any]]:
    wanted: dict[int, tuple[PairKey, str]] = {}
    for key, before, after in selected:
        wanted[before] = (key, "before")
        wanted[after] = (key, "after")
    final_index = max(wanted)
    columns = ["card", "hand", "elixir", "png_bytes", "x", "y", "arena", "replay", "frame", "offset"]
    output: dict[PairKey, dict[str, Any]] = {}
    source_index = 0
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(columns=columns, batch_size=batch_size, use_threads=False):
        payload = batch.to_pydict()
        for local_index in range(batch.num_rows):
            if source_index in wanted:
                key, side = wanted[source_index]
                row = {name: payload[name][local_index] for name in columns if name != "png_bytes"}
                row["image"] = np.asarray(
                    Image.open(io.BytesIO(payload["png_bytes"][local_index])).convert("RGB")
                )[..., ::-1].copy()
                output.setdefault(key, {})[side] = row
            source_index += 1
        if source_index > final_index:
            break
    return output


def main() -> None:
    args = parse_args()
    if args.samples <= 0 or args.batch_size <= 0:
        raise ValueError("samples and batch size must be positive")
    source = Path(args.input_parquet).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    converter = TVRoyalePlacementConverter(decks_path=args.decks_path)
    candidates, skipped = _candidate_pairs(source, converter, max_pairs=None)
    selected = _select_candidates(candidates, args.samples)
    rows = _load_rows(source, selected, batch_size=args.parquet_batch_size)
    models = _load_detector_models(
        [Path(value).resolve() for value in args.detector_weight],
        Path(args.katacr_source_root).resolve(),
    )

    summary = []
    for start in range(0, len(selected), args.batch_size):
        chunk = selected[start : start + args.batch_size]
        images = [rows[key][side]["image"] for key, _, _ in chunk for side in ("before", "after")]
        per_model_results = [
            model.predict(
                images,
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
        for chunk_index, (key, _, _) in enumerate(chunk):
            before_detections = _combined_detections(
                [result[chunk_index * 2] for result in per_model_results],
                models,
                nms_iou=args.nms_iou,
            )
            after_detections = _combined_detections(
                [result[chunk_index * 2 + 1] for result in per_model_results],
                models,
                nms_iou=args.nms_iou,
            )
            recovered = recover_deployment_clock(
                before_detections,
                after_detections,
                minimum_confidence=args.clock_confidence,
                existing_match_distance=args.existing_clock_distance,
                cluster_distance=args.clock_cluster_distance,
            )
            before = rows[key]["before"]
            canvases = [before["image"].copy(), rows[key]["after"]["image"].copy()]
            for canvas in canvases:
                _draw_grid(canvas)
            _draw_detections(canvases[0], before_detections)
            _draw_detections(canvases[1], after_detections)
            direct_x = int(before["x"])
            direct_y = int(before["y"])
            direct_tile = (
                converter.source_pixel_to_canonical_tile(direct_x, direct_y)
                if direct_x >= 0 and direct_y >= 0
                else None
            )
            if direct_tile is not None:
                for canvas in canvases:
                    _draw_location(
                        canvas,
                        x=direct_x,
                        y=direct_y,
                        tile=direct_tile,
                        color=(40, 40, 255),
                        label="source",
                    )
            recovered_tile = None
            distance = None
            if recovered is not None:
                rx, ry = round(recovered.x), round(recovered.y)
                recovered_tile = converter.source_pixel_to_canonical_tile(rx, ry)
                if direct_tile is not None:
                    distance = float(np.hypot(rx - direct_x, ry - direct_y))
                for canvas in canvases:
                    _draw_location(
                        canvas,
                        x=rx,
                        y=ry,
                        tile=recovered_tile,
                        color=(30, 255, 30),
                        label="clock",
                    )
            header = np.zeros((82, IMAGE_WIDTH * 2, 3), dtype=np.uint8)
            if recovered is None:
                status = f"clock=missing source_tile={direct_tile}"
            elif distance is None:
                status = f"source=missing clock_tile={recovered_tile}"
            else:
                status = (
                    f"source_tile={direct_tile} clock_tile={recovered_tile} "
                    f"pixels={distance:.1f}"
                )
            cv2.putText(header, f"{before['arena']} {key[0]} frame={key[1]} card={key[2]}", (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(header, status, (8, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(header, "outline=detector pixels, NOT hitbox; dot=entity position; crosses=placement labels", (8, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (210, 210, 210), 1, cv2.LINE_AA)
            result = np.concatenate((header, np.concatenate(canvases, axis=1)), axis=0)
            output = output_dir / f"{start + chunk_index:04d}_{before['arena']}_{key[1]}_{key[2]}.jpg"
            cv2.imwrite(str(output), result, [cv2.IMWRITE_JPEG_QUALITY, 94])
            summary.append(
                {
                    "output": str(output),
                    "arena": str(before["arena"]),
                    "replay": key[0],
                    "frame": key[1],
                    "card": key[2],
                    "source_tile": direct_tile,
                    "clock_tile": recovered_tile,
                    "pixel_distance": distance,
                    "tile_match": (
                        direct_tile == recovered_tile
                        if direct_tile is not None and recovered_tile is not None
                        else None
                    ),
                    "before_detections": len(before_detections),
                    "after_detections": len(after_detections),
                }
            )
    manifest = {
        "source": str(source),
        "candidate_pairs": len(candidates),
        "initial_skipped": skipped,
        "samples": summary,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
