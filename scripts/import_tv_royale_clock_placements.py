from __future__ import annotations

# mypy: disable-error-code="import-not-found,import-untyped"
import argparse
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from import_tv_royale_placements import (
    _build_corpus,
    _combined_detections,
    _load_detector_models,
)

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256
from clasher.rl.tv_royale_replay import (
    SOURCE_ARENA_MIDDLE_Y,
    TVRoyalePlacementConverter,
    recover_deployment_clock,
)

PairKey = tuple[str, int, str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recover human placement labels from the new deployment clock in "
            "paired before/after TV Royale frames"
        )
    )
    parser.add_argument("--input-parquet", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--katacr-source-root", default="datasets/external/KataCR")
    parser.add_argument("--detector-weight", action="append", required=True)
    parser.add_argument("--device", choices=["cpu", "mps", "cuda"], default="mps")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--parquet-batch-size", type=int, default=32)
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--nms-iou", type=float, default=0.6)
    parser.add_argument("--clock-confidence", type=float, default=0.75)
    parser.add_argument("--existing-clock-distance", type=float, default=24.0)
    parser.add_argument("--clock-cluster-distance", type=float, default=18.0)
    parser.add_argument("--max-entities", type=int, default=128)
    parser.add_argument("--max-pairs", type=int, default=None)
    parser.add_argument(
        "--arena",
        action="append",
        help="limit conversion to one or more source arena labels",
    )
    parser.add_argument("--audit-dir", default=None)
    parser.add_argument("--audit-samples", type=int, default=0)
    parser.add_argument("--seed", type=int, default=1_022_001)
    return parser.parse_args()


def _candidate_pairs(
    parquet_path: Path,
    converter: TVRoyalePlacementConverter,
    *,
    max_pairs: int | None,
    allowed_arenas: set[str] | None = None,
) -> tuple[list[tuple[PairKey, int, int]], dict[str, int]]:
    import pyarrow.parquet as pq

    columns = ["card", "hand", "replay", "frame", "offset", "arena"]
    table = pq.read_table(parquet_path, columns=columns)
    payload = table.to_pydict()
    indices_by_key: dict[PairKey, dict[int, int]] = {}
    before_index_by_key: dict[PairKey, int] = {}
    skipped: Counter[str] = Counter()
    for index in range(table.num_rows):
        key = (
            str(payload["replay"][index]),
            int(payload["frame"][index]),
            str(payload["card"][index]),
        )
        offset = int(payload["offset"][index])
        offsets = indices_by_key.setdefault(key, {})
        if offset in offsets:
            skipped["duplicate_source_row"] += 1
            continue
        offsets[offset] = index
        if offset == 0:
            before_index_by_key[key] = index

    candidates_by_frame: dict[tuple[str, int], tuple[PairKey, int, int]] = {}
    conflicting_frames: set[tuple[str, int]] = set()
    for key, before_index in sorted(
        before_index_by_key.items(), key=lambda item: item[1]
    ):
        if (
            allowed_arenas is not None
            and str(payload["arena"][before_index]) not in allowed_arenas
        ):
            skipped["outside_selected_arena"] += 1
            continue
        offsets = indices_by_key[key]
        if 1 not in offsets:
            skipped["missing_after_pair"] += 1
            continue
        hand = payload["hand"][before_index]
        values = list(hand) if isinstance(hand, list) else []
        if len(values) != 4:
            skipped["incomplete_hand"] += 1
            continue
        target = converter.source_card_name(payload["card"][before_index])
        if target is None:
            skipped["outside_enabled_vocabulary"] += 1
            continue
        if target not in [converter.source_card_name(value) for value in values]:
            skipped["target_not_in_hand"] += 1
            continue
        if converter.source_card_type(payload["card"][before_index]) == "spell":
            skipped["spell_location_label"] += 1
            continue
        frame_key = (key[0], key[1])
        if frame_key in conflicting_frames:
            skipped["conflicting_frame_labels"] += 1
            continue
        previous = candidates_by_frame.get(frame_key)
        if previous is not None:
            candidates_by_frame.pop(frame_key)
            conflicting_frames.add(frame_key)
            skipped["conflicting_frame_labels"] += 2
            continue
        candidates_by_frame[frame_key] = (key, before_index, offsets[1])
    candidates = sorted(candidates_by_frame.values(), key=lambda item: item[1])
    if max_pairs is not None:
        candidates = candidates[:max_pairs]
    return candidates, dict(sorted(skipped.items()))


def _collect_clock_rows(
    *,
    parquet_path: Path,
    converter: TVRoyalePlacementConverter,
    models: list[Any],
    candidate_pairs: list[tuple[PairKey, int, int]],
    device: str,
    inference_batch_size: int,
    parquet_batch_size: int,
    confidence: float,
    nms_iou: float,
    clock_confidence: float,
    existing_clock_distance: float,
    clock_cluster_distance: float,
    audit_dir: Path | None,
    audit_samples: int,
) -> tuple[
    list[dict[str, Any]],
    dict[str, int],
    list[float],
    list[int],
    list[float],
    list[bool],
]:
    import pyarrow.parquet as pq
    from PIL import Image

    pair_by_index: dict[int, tuple[PairKey, bool]] = {}
    for key, before_index, after_index in candidate_pairs:
        pair_by_index[before_index] = (key, True)
        pair_by_index[after_index] = (key, False)
    selected_indices = set(pair_by_index)
    rows_by_key: dict[PairKey, dict[str, Any]] = {}
    images_by_key: dict[PairKey, dict[str, np.ndarray]] = {}
    ready: list[PairKey] = []
    collected: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    clock_confidences: list[float] = []
    clock_supports: list[int] = []
    direct_label_distances: list[float] = []
    direct_label_tile_matches: list[bool] = []
    audit_written = 0
    if audit_dir is not None:
        audit_dir.mkdir(parents=True, exist_ok=True)
    columns = [
        "card",
        "hand",
        "elixir",
        "png_bytes",
        "x",
        "y",
        "arena",
        "replay",
        "frame",
        "offset",
    ]

    def flush() -> None:
        nonlocal audit_written
        if not ready:
            return
        keys = list(ready)
        images = [
            images_by_key[key][side] for key in keys for side in ("before", "after")
        ]
        per_model_results = [
            model.predict(
                images,
                device=device,
                verbose=False,
                conf=confidence,
                iou=nms_iou,
                imgsz=(896, 576),
            )
            for model in models
        ]
        for pair_index, key in enumerate(keys):
            before_detections = _combined_detections(
                [results[pair_index * 2] for results in per_model_results],
                models,
                nms_iou=nms_iou,
            )
            after_detections = _combined_detections(
                [results[pair_index * 2 + 1] for results in per_model_results],
                models,
                nms_iou=nms_iou,
            )
            recovered = recover_deployment_clock(
                before_detections,
                after_detections,
                minimum_confidence=clock_confidence,
                existing_match_distance=existing_clock_distance,
                cluster_distance=clock_cluster_distance,
            )
            if recovered is None:
                skipped["clock_recovery_failed"] += 1
                continue
            x = round(recovered.x)
            y = round(recovered.y)
            if y <= SOURCE_ARENA_MIDDLE_Y:
                skipped["non_lower_side_clock"] += 1
                continue
            raw_row = rows_by_key[key]
            accepted, reason = converter.is_location_training_candidate(
                raw_card=raw_row["card"],
                raw_hand=raw_row["hand"],
                elixir=float(raw_row["elixir"]),
                x=x,
                y=y,
            )
            if not accepted:
                skipped[reason or "invalid_recovered_location"] += 1
                continue
            converted = converter.convert(
                raw_card=str(raw_row["card"]),
                raw_hand=raw_row["hand"],
                elixir=float(raw_row["elixir"]),
                frame=int(raw_row["frame"]),
                x=x,
                y=y,
                detections=before_detections,
            )
            if converted is None:
                skipped["conversion_failed"] += 1
                continue
            collected.append(
                {
                    "source_index": int(raw_row["source_index"]),
                    "arena": str(raw_row["arena"]),
                    "replay": str(raw_row["replay"]),
                    "frame": int(raw_row["frame"]),
                    "converted": converted,
                }
            )
            clock_confidences.append(recovered.confidence)
            clock_supports.append(recovered.support)
            direct_x = int(raw_row["x"])
            direct_y = int(raw_row["y"])
            if direct_x >= 0 and direct_y >= 0:
                direct_label_distances.append(
                    float(np.hypot(x - direct_x, y - direct_y))
                )
                direct_label_tile_matches.append(
                    converter.source_pixel_to_canonical_tile(x, y)
                    == converter.source_pixel_to_canonical_tile(direct_x, direct_y)
                )
            if audit_dir is not None and audit_written < audit_samples:
                import cv2

                before_image = images_by_key[key]["before"].copy()
                after_image = images_by_key[key]["after"].copy()
                for image in (before_image, after_image):
                    cv2.circle(image, (x, y), 12, (0, 255, 0), 3)
                if direct_x >= 0 and direct_y >= 0:
                    cv2.circle(before_image, (direct_x, direct_y), 9, (0, 0, 255), 2)
                canvas = np.concatenate((before_image, after_image), axis=1)
                cv2.putText(
                    canvas,
                    f"green=clock red=direct {raw_row['card']} conf={recovered.confidence:.2f}",
                    (8, 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                cv2.imwrite(
                    str(audit_dir / f"{audit_written:04d}_{key[1]}_{key[2]}.jpg"),
                    canvas,
                )
                audit_written += 1
        for key in keys:
            rows_by_key.pop(key, None)
            images_by_key.pop(key, None)
        ready.clear()
        print(
            json.dumps(
                {
                    "detected_pairs": len(collected) + sum(skipped.values()),
                    "converted_rows": len(collected),
                    "skipped": dict(sorted(skipped.items())),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    source_index = 0
    final_selected_index = max(selected_indices)
    parquet = pq.ParquetFile(parquet_path)
    for record_batch in parquet.iter_batches(
        batch_size=parquet_batch_size, columns=columns, use_threads=False
    ):
        payload = record_batch.to_pydict()
        for local_index in range(record_batch.num_rows):
            if source_index in selected_indices:
                key, is_before = pair_by_index[source_index]
                side = "before" if is_before else "after"
                image = np.asarray(
                    Image.open(io.BytesIO(payload["png_bytes"][local_index])).convert(
                        "RGB"
                    )
                )[..., ::-1].copy()
                images_by_key.setdefault(key, {})[side] = image
                if is_before:
                    rows_by_key[key] = {
                        name: payload[name][local_index]
                        for name in columns
                        if name != "png_bytes"
                    }
                    rows_by_key[key]["source_index"] = source_index
                if len(images_by_key[key]) == 2:
                    ready.append(key)
                    if len(ready) >= inference_batch_size:
                        flush()
            source_index += 1
        if source_index > final_selected_index:
            break
    flush()
    return (
        collected,
        dict(sorted(skipped.items())),
        clock_confidences,
        clock_supports,
        direct_label_distances,
        direct_label_tile_matches,
    )


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0 or args.parquet_batch_size <= 0:
        raise ValueError("batch sizes must be positive")
    if args.max_pairs is not None and args.max_pairs <= 0:
        raise ValueError("--max-pairs must be positive")
    if args.audit_samples < 0:
        raise ValueError("--audit-samples must be non-negative")
    for name in ("confidence", "nms_iou", "clock_confidence"):
        value = float(getattr(args, name))
        if not 0.0 < value <= 1.0:
            raise ValueError(f"--{name.replace('_', '-')} must be in (0, 1]")
    parquet_path = resolve_path(args.input_parquet, must_exist=True)
    output_path = resolve_path(args.output)
    manifest_path = resolve_path(args.manifest_out)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    katacr_source_root = resolve_path(args.katacr_source_root, must_exist=True)
    weights = [resolve_path(value, must_exist=True) for value in args.detector_weight]
    audit_dir = resolve_path(args.audit_dir) if args.audit_dir else None
    converter = TVRoyalePlacementConverter(
        decks_path=str(decks_path), max_entities=args.max_entities
    )
    candidates, initial_skipped = _candidate_pairs(
        parquet_path,
        converter,
        max_pairs=args.max_pairs,
        allowed_arenas=set(args.arena) if args.arena else None,
    )
    if not candidates:
        raise ValueError("source contains no supported before/after placement pairs")
    print(
        json.dumps(
            {
                "candidate_pairs": len(candidates),
                "skipped": initial_skipped,
                "device": args.device,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    models = _load_detector_models(weights, katacr_source_root)
    (
        rows,
        recovery_skipped,
        clock_confidences,
        clock_supports,
        direct_label_distances,
        direct_label_tile_matches,
    ) = _collect_clock_rows(
        parquet_path=parquet_path,
        converter=converter,
        models=models,
        candidate_pairs=candidates,
        device=args.device,
        inference_batch_size=args.batch_size,
        parquet_batch_size=args.parquet_batch_size,
        confidence=args.confidence,
        nms_iou=args.nms_iou,
        clock_confidence=args.clock_confidence,
        existing_clock_distance=args.existing_clock_distance,
        clock_cluster_distance=args.clock_cluster_distance,
        audit_dir=audit_dir,
        audit_samples=args.audit_samples,
    )
    payload, statistics = _build_corpus(
        rows,
        converter=converter,
        source_path=parquet_path,
        seed=args.seed,
        label_source="tv-royale-human-deployment-clock",
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
        "candidate_pairs": len(candidates),
        "initial_skipped": initial_skipped,
        "recovery_skipped": recovery_skipped,
        "detector_device": args.device,
        "detector_confidence": args.confidence,
        "detector_nms_iou": args.nms_iou,
        "clock_confidence": args.clock_confidence,
        "existing_clock_distance": args.existing_clock_distance,
        "clock_cluster_distance": args.clock_cluster_distance,
        "clock_confidence_mean": float(np.mean(clock_confidences)),
        "clock_confidence_min": float(np.min(clock_confidences)),
        "clock_support_mean": float(np.mean(clock_supports)),
        "direct_label_comparisons": len(direct_label_distances),
        "direct_label_distance_mean": (
            float(np.mean(direct_label_distances))
            if direct_label_distances
            else None
        ),
        "direct_label_distance_median": (
            float(np.median(direct_label_distances))
            if direct_label_distances
            else None
        ),
        "direct_label_tile_match_rate": (
            float(np.mean(direct_label_tile_matches))
            if direct_label_tile_matches
            else None
        ),
        "max_pairs": args.max_pairs,
        "audit_dir": str(audit_dir) if audit_dir is not None else None,
        "audit_samples": args.audit_samples,
    }
    atomic_write_json(manifest_path, manifest)
    print(json.dumps(manifest, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
