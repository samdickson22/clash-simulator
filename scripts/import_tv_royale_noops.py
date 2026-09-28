from __future__ import annotations

# mypy: disable-error-code="import-not-found,import-untyped"
import argparse
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from import_tv_royale_placements import (  # type: ignore[import-not-found]
    _build_corpus,
    _combined_detections,
    _load_detector_models,
)

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256
from clasher.rl.tv_royale_replay import (  # type: ignore[import-untyped]
    TVRoyalePlacementConverter,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build explicit human wait/no-op rehearsal from MIT-licensed "
            "TV Royale no-card-play frames"
        )
    )
    parser.add_argument("--input-parquet", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--katacr-source-root", default="datasets/external/KataCR")
    parser.add_argument(
        "--detector-weight",
        action="append",
        required=True,
        help="repeat for each compatible KataCR detector checkpoint",
    )
    parser.add_argument("--device", choices=["cpu", "mps", "cuda"], default="mps")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--parquet-batch-size", type=int, default=64)
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--nms-iou", type=float, default=0.6)
    parser.add_argument("--max-entities", type=int, default=128)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1_032_001)
    return parser.parse_args()


def _candidate_indices(
    parquet_path: Path,
    converter: TVRoyalePlacementConverter,
    *,
    max_rows: int | None,
) -> tuple[list[int], dict[str, int]]:
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    table = pq.read_table(
        parquet_path,
        columns=["replay", "frame", "card", "hand", "offset"],
    )
    payload = table.to_pydict()
    candidates: list[int] = []
    skipped: Counter[str] = Counter()
    seen_frames: set[tuple[str, int, int]] = set()
    for index in range(table.num_rows):
        if int(payload["offset"][index]) != 0:
            skipped["offset_augmentation"] += 1
            continue
        accepted, reason = converter.is_noop_training_candidate(
            raw_card=payload["card"][index],
            raw_hand=payload["hand"][index],
        )
        if not accepted:
            assert reason is not None
            skipped[reason] += 1
            continue
        frame_key = (
            str(payload["replay"][index]),
            int(payload["frame"][index]),
            int(payload["offset"][index]),
        )
        if frame_key in seen_frames:
            skipped["duplicate_source_frame"] += 1
            continue
        seen_frames.add(frame_key)
        candidates.append(index)
        if max_rows is not None and len(candidates) >= max_rows:
            break
    return candidates, dict(sorted(skipped.items()))


def _collect_rows(
    *,
    parquet_path: Path,
    converter: TVRoyalePlacementConverter,
    models: list[Any],
    candidate_indices: list[int],
    device: str,
    inference_batch_size: int,
    parquet_batch_size: int,
    confidence: float,
    nms_iou: float,
) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq  # type: ignore[import-untyped]
    from PIL import Image

    selected = set(candidate_indices)
    final_selected_index = max(selected)
    collected: list[dict[str, Any]] = []
    columns = [
        "card",
        "hand",
        "elixir",
        "png_bytes",
        "arena",
        "replay",
        "frame",
        "offset",
    ]
    source_index = 0
    parquet = pq.ParquetFile(parquet_path)
    pending_rows: list[dict[str, Any]] = []
    pending_images: list[np.ndarray] = []

    def flush() -> None:
        if not pending_rows:
            return
        per_model_results = [
            model.predict(
                pending_images,
                device=device,
                verbose=False,
                conf=confidence,
                iou=nms_iou,
                imgsz=(896, 576),
            )
            for model in models
        ]
        for row_index, raw_row in enumerate(pending_rows):
            detections = _combined_detections(
                [results[row_index] for results in per_model_results],
                models,
                nms_iou=nms_iou,
            )
            converted = converter.convert_noop(
                raw_card=str(raw_row["card"]),
                raw_hand=raw_row["hand"],
                elixir=float(raw_row["elixir"]),
                frame=int(raw_row["frame"]),
                detections=detections,
            )
            if converted is not None:
                collected.append(
                    {
                        "source_index": int(raw_row["source_index"]),
                        "arena": str(raw_row["arena"]),
                        "replay": str(raw_row["replay"]),
                        "frame": int(raw_row["frame"]),
                        "converted": converted,
                    }
                )
        pending_rows.clear()
        pending_images.clear()
        print(
            json.dumps(
                {
                    "processed_source_rows": min(
                        source_index, final_selected_index + 1
                    ),
                    "converted_rows": len(collected),
                }
            ),
            flush=True,
        )

    for record_batch in parquet.iter_batches(
        batch_size=parquet_batch_size,
        columns=columns,
        use_threads=False,
    ):
        payload = record_batch.to_pydict()
        for local_index in range(record_batch.num_rows):
            if source_index in selected:
                raw_row = {
                    name: payload[name][local_index]
                    for name in columns
                    if name != "png_bytes"
                }
                raw_row["source_index"] = source_index
                image = np.asarray(
                    Image.open(io.BytesIO(payload["png_bytes"][local_index])).convert(
                        "RGB"
                    )
                )[..., ::-1].copy()
                pending_rows.append(raw_row)
                pending_images.append(image)
                if len(pending_rows) >= inference_batch_size:
                    flush()
            source_index += 1
        if source_index > final_selected_index:
            break
    flush()
    return collected


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0 or args.parquet_batch_size <= 0:
        raise ValueError("batch sizes must be positive")
    if args.max_rows is not None and args.max_rows <= 0:
        raise ValueError("--max-rows must be positive")
    if not 0.0 < args.confidence <= 1.0 or not 0.0 < args.nms_iou <= 1.0:
        raise ValueError("confidence and NMS IoU must be in (0, 1]")

    parquet_path = resolve_path(args.input_parquet, must_exist=True)
    output_path = resolve_path(args.output)
    manifest_path = resolve_path(args.manifest_out)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    katacr_source_root = resolve_path(args.katacr_source_root, must_exist=True)
    weights = [resolve_path(value, must_exist=True) for value in args.detector_weight]
    converter = TVRoyalePlacementConverter(
        decks_path=str(decks_path), max_entities=args.max_entities
    )
    candidate_indices, skipped = _candidate_indices(
        parquet_path, converter, max_rows=args.max_rows
    )
    if not candidate_indices:
        raise ValueError("source contains no supported explicit no-op rows")
    print(
        json.dumps(
            {
                "candidate_rows": len(candidate_indices),
                "skipped": skipped,
                "device": args.device,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    models = _load_detector_models(weights, katacr_source_root)
    rows = _collect_rows(
        parquet_path=parquet_path,
        converter=converter,
        models=models,
        candidate_indices=candidate_indices,
        device=args.device,
        inference_batch_size=args.batch_size,
        parquet_batch_size=args.parquet_batch_size,
        confidence=args.confidence,
        nms_iou=args.nms_iou,
    )
    payload, statistics = _build_corpus(
        rows,
        converter=converter,
        source_path=parquet_path,
        seed=args.seed,
        label_source="tv-royale-human-noop",
    )
    atomic_save_npz(output_path, payload)
    manifest = {
        **statistics,
        "output": str(output_path),
        "output_sha256": file_sha256(output_path),
        "detectors": [
            {"path": str(weight), "sha256": file_sha256(weight)}
            for weight in weights
        ],
        "candidate_rows": len(candidate_indices),
        "skipped": skipped,
        "detector_device": args.device,
        "detector_confidence": args.confidence,
        "detector_nms_iou": args.nms_iou,
        "max_rows": args.max_rows,
    }
    atomic_write_json(manifest_path, manifest)
    print(json.dumps(manifest, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
