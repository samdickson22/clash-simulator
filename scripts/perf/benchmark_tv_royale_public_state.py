from __future__ import annotations

# mypy: disable-error-code="import-not-found,import-untyped"
import argparse
import hashlib
import json
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pyarrow.parquet as pq

from clasher.rl.oracle_corpus import atomic_write_json
from clasher.rl.tv_royale_public_state import (
    TVRoyaleEntityHealthObservation,
    TVRoyaleHealthObservation,
    associate_health_to_entities,
    measure_health_bars,
    render_entity_health_observations,
    render_health_observations,
)
from clasher.rl.tv_royale_replay import TVRoyalePlacementConverter
from scripts.extract_tv_royale_raw_cascade import _detect, _selected_crops
from scripts.import_tv_royale_placements import _load_detector_models


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark visible HP extraction from TV Royale frames"
    )
    parser.add_argument("--input-parquet", required=True)
    parser.add_argument("--katacr-source-root", default="datasets/external/KataCR")
    parser.add_argument("--detector-weight", action="append", required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--frames", type=int, default=64)
    parser.add_argument("--scan-repetitions", type=int, default=200)
    parser.add_argument("--audit-samples", type=int, default=12)
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--nms-iou", type=float, default=0.6)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args()


def _digest(observations: list[tuple[int, TVRoyaleHealthObservation]]) -> str:
    digest = hashlib.sha256()
    for frame, observation in observations:
        digest.update(
            (
                f"{frame}|{observation.bar_class}|{observation.belonging}|"
                f"{observation.fill_fraction:.8f}|{observation.confidence:.8f}|"
                f"{observation.x1:.2f}|{observation.y1:.2f}|"
                f"{observation.x2:.2f}|{observation.y2:.2f}\n"
            ).encode()
        )
    return digest.hexdigest()


def _entity_digest(
    observations: list[tuple[int, TVRoyaleEntityHealthObservation]],
) -> str:
    digest = hashlib.sha256()
    for frame, observation in observations:
        digest.update(
            (
                f"{frame}|{observation.entity_index}|{observation.entity_class}|"
                f"{observation.belonging}|{observation.center_x:.2f}|"
                f"{observation.center_y:.2f}|{observation.fill_fraction:.8f}|"
                f"{observation.confidence:.8f}\n"
            ).encode()
        )
    return digest.hexdigest()


def _summary(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": float(array.size),
        "minimum": float(array.min()),
        "median": float(np.median(array)),
        "mean": float(array.mean()),
        "maximum": float(array.max()),
    }


def main() -> None:
    args = parse_args()
    if args.frames <= 0 or args.scan_repetitions < 2 or args.audit_samples <= 0:
        raise ValueError("frames/audits must be positive and repetitions >= 2")
    source = Path(args.input_parquet).resolve()
    total = pq.ParquetFile(source).metadata.num_rows
    count = min(args.frames, total)
    frame_ids = np.linspace(0, total - 1, count, dtype=np.int64).tolist()
    crops = _selected_crops(source, set(frame_ids), batch_size=128)

    models = _load_detector_models(
        [Path(value).resolve() for value in args.detector_weight],
        Path(args.katacr_source_root).resolve(),
    )
    detector_start = time.perf_counter()
    detections = _detect(
        models,
        crops,
        device=args.device,
        batch_size=args.batch_size,
        confidence=args.confidence,
        nms_iou=args.nms_iou,
    )
    detector_seconds = time.perf_counter() - detector_start
    converter = TVRoyalePlacementConverter()

    def visible_body_class(class_name: str) -> bool:
        return converter.is_supported_public_body_class(class_name)

    scan_durations: list[float] = []
    final: list[tuple[int, TVRoyaleHealthObservation]] = []
    final_entities: list[tuple[int, TVRoyaleEntityHealthObservation]] = []
    for _ in range(args.scan_repetitions):
        rows: list[tuple[int, TVRoyaleHealthObservation]] = []
        entity_rows: list[tuple[int, TVRoyaleEntityHealthObservation]] = []
        start = time.perf_counter()
        for frame in frame_ids:
            rows.extend(
                (frame, observation)
                for observation in measure_health_bars(
                    crops[frame], detections[frame]
                )
            )
            entity_rows.extend(
                (frame, observation)
                for observation in associate_health_to_entities(
                    crops[frame],
                    detections[frame],
                    body_class_predicate=visible_body_class,
                )
            )
        scan_durations.append(time.perf_counter() - start)
        final = rows
        final_entities = entity_rows

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_indices = np.linspace(
        0, len(frame_ids) - 1, min(args.audit_samples, len(frame_ids)), dtype=np.int64
    )
    audit_paths: list[str] = []
    rows_by_frame: dict[int, list[TVRoyaleHealthObservation]] = {
        frame: [] for frame in frame_ids
    }
    entities_by_frame: dict[int, list[TVRoyaleEntityHealthObservation]] = {
        frame: [] for frame in frame_ids
    }
    for frame, observation in final:
        rows_by_frame[frame].append(observation)
    for frame, observation in final_entities:
        entities_by_frame[frame].append(observation)
    for audit_index, frame_index in enumerate(audit_indices.tolist()):
        frame = frame_ids[frame_index]
        if entities_by_frame[frame]:
            rendered = render_entity_health_observations(
                crops[frame], entities_by_frame[frame]
            )
        else:
            rendered = render_health_observations(crops[frame], rows_by_frame[frame])
        rendered = cv2.resize(
            rendered, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_NEAREST
        )
        path = output_dir / f"{audit_index:04d}_frame_{frame:05d}.jpg"
        if not cv2.imwrite(str(path), rendered):
            raise OSError(f"failed to write {path}")
        audit_paths.append(str(path))

    class_counts = Counter(row.bar_class for _, row in final)
    team_counts = Counter(row.belonging for _, row in final)
    fractions_by_class = {
        class_name: _summary(
            [row.fill_fraction for _, row in final if row.bar_class == class_name]
        )
        for class_name in sorted(class_counts)
    }
    median_scan = statistics.median(scan_durations)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "source": str(source),
        "source_rows": total,
        "sampled_frames": len(frame_ids),
        "frame_ids": frame_ids,
        "device": args.device,
        "batch_size": args.batch_size,
        "detector_seconds": detector_seconds,
        "detector_frames_per_second": len(frame_ids) / detector_seconds,
        "health_observations": len(final),
        "health_observations_by_class": dict(class_counts),
        "health_observations_by_team": {
            str(key): value for key, value in sorted(team_counts.items())
        },
        "health_fraction_by_class": fractions_by_class,
        "health_digest": _digest(final),
        "associated_entity_health_observations": len(final_entities),
        "associated_entity_classes": dict(
            Counter(row.entity_class for _, row in final_entities)
        ),
        "associated_entity_health_digest": _entity_digest(final_entities),
        "scan_repetitions": args.scan_repetitions,
        "scan_durations_seconds": scan_durations,
        "scan_median_seconds": median_scan,
        "scan_frames_per_second": len(frame_ids) / median_scan,
        "audit_paths": audit_paths,
    }
    atomic_write_json(Path(args.report).resolve(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
