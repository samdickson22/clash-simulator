from __future__ import annotations

# mypy: disable-error-code="import-not-found,import-untyped"
import argparse
import io
import json
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.imitation import CORPUS_SCHEMA_VERSION, CorpusMetadata
from clasher.rl.oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.tv_royale_replay import (
    TVRoyaleDetection,
    TVRoyalePlacementConverter,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build state-conditioned placement rehearsal from MIT-licensed "
            "TV Royale action frames"
        )
    )
    parser.add_argument("--input-parquet", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument(
        "--katacr-source-root", default="datasets/external/KataCR"
    )
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
    parser.add_argument("--seed", type=int, default=1_017_001)
    return parser.parse_args()


def _load_detector_models(
    weights: list[Path], katacr_source_root: Path
) -> list[Any]:
    # The checkpoints are pinned, trusted public KataCR artifacts. Torch 2.6+
    # otherwise defaults to weights_only=True and refuses their custom model
    # class before the class can be imported.
    sys.path.insert(0, str(katacr_source_root))
    original_torch_load = torch.load

    def trusted_torch_load(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("weights_only", False)
        return original_torch_load(*args, **kwargs)

    torch.load = trusted_torch_load  # type: ignore[assignment]
    try:
        from katacr.yolov8.custom_model import (
            CRDetectionModel,  # type: ignore[import-not-found]
        )
        from katacr.yolov8.custom_predict import (  # type: ignore[import-not-found]
            CRDetectionPredictor,
        )
        from ultralytics.engine.model import Model  # type: ignore[import-untyped]
        from ultralytics.models.yolo.detect import (  # type: ignore[import-untyped]
            DetectionTrainer,
            DetectionValidator,
        )

        class InferenceOnlyYOLOCR(Model):
            @property
            def task_map(self) -> dict[str, dict[str, Any]]:
                return {
                    "detect": {
                        "model": CRDetectionModel,
                        "trainer": DetectionTrainer,
                        "validator": DetectionValidator,
                        "predictor": CRDetectionPredictor,
                    }
                }

        return [InferenceOnlyYOLOCR(str(weight)) for weight in weights]
    finally:
        torch.load = original_torch_load  # type: ignore[assignment]


def _combined_detections(
    results: list[Any],
    models: list[Any],
    *,
    nms_iou: float,
    nms_backend: str = "auto",
) -> list[TVRoyaleDetection]:
    """Merge detector outputs and apply cross-model NMS.

    The reference implementation copied every proposal to Python, rebuilt a
    CPU tensor, and then ran NMS.  CUDA inference can keep the proposals on the
    accelerator and transfer only the retained rows.  CPU remains the exact
    fallback for CPU/MPS results, while ``shadow`` compares both paths before
    returning the native result.
    """

    if nms_backend not in {"auto", "cpu", "native", "shadow"}:
        raise ValueError(f"unsupported detection NMS backend: {nms_backend}")

    source_rows = [result.orig_boxes.detach() for result in results]
    nonempty = [rows for rows in source_rows if rows.numel()]
    if not nonempty:
        return []

    same_device = all(rows.device == nonempty[0].device for rows in nonempty)
    native_supported = same_device and nonempty[0].device.type in {"cpu", "cuda"}
    use_native = nms_backend in {"native", "shadow"} or (
        nms_backend == "auto" and nonempty[0].device.type == "cuda"
    )
    if use_native and not native_supported:
        if nms_backend in {"native", "shadow"}:
            raise ValueError(
                "native detection NMS requires all nonempty tensors on CPU or CUDA"
            )
        use_native = False

    native = _combined_detections_tensorized(
        source_rows,
        models,
        nms_iou=nms_iou,
        force_cpu=not use_native,
    )
    if nms_backend == "shadow":
        reference = _combined_detections_reference(
            source_rows,
            models,
            nms_iou=nms_iou,
        )
        if native != reference:
            raise RuntimeError(
                "native detection NMS diverged from the CPU reference: "
                f"native={native!r}, reference={reference!r}"
            )
    return native


def _combined_detections_tensorized(
    source_rows: list[torch.Tensor],
    models: list[Any],
    *,
    nms_iou: float,
    force_cpu: bool,
) -> list[TVRoyaleDetection]:
    from torchvision.ops import nms  # type: ignore[import-untyped]

    nonempty: list[torch.Tensor] = []
    model_indices: list[torch.Tensor] = []
    target_device = torch.device("cpu") if force_cpu else next(
        rows.device for rows in source_rows if rows.numel()
    )
    for model_index, rows in enumerate(source_rows):
        if not rows.numel():
            continue
        selected = rows.to(device=target_device, dtype=torch.float32)
        nonempty.append(selected)
        model_indices.append(
            torch.full(
                (selected.shape[0],),
                model_index,
                dtype=torch.int64,
                device=target_device,
            )
        )
    if not nonempty:
        return []
    merged = torch.cat(nonempty, dim=0)
    merged_models = torch.cat(model_indices, dim=0)
    keep = nms(merged[:, :4], merged[:, 4], nms_iou)
    kept_rows = merged.index_select(0, keep).cpu().tolist()
    kept_models = merged_models.index_select(0, keep).cpu().tolist()
    output: list[TVRoyaleDetection] = []
    for row, model_index in zip(kept_rows, kept_models, strict=True):
        x1, y1, x2, y2, confidence, class_id, belonging = row
        output.append(
            TVRoyaleDetection(
                class_name=str(models[int(model_index)].names[int(class_id)]),
                belonging=int(belonging),
                confidence=float(confidence),
                x1=float(x1),
                y1=float(y1),
                x2=float(x2),
                y2=float(y2),
            )
        )
    return output


def _combined_detections_reference(
    source_rows: list[torch.Tensor],
    models: list[Any],
    *,
    nms_iou: float,
) -> list[TVRoyaleDetection]:
    """Original Python/CPU implementation retained as a parity oracle."""

    from torchvision.ops import nms  # type: ignore[import-untyped]

    detections: list[tuple[list[float], str, int, float]] = []
    for rows, model in zip(source_rows, models, strict=True):
        for row in rows.cpu().tolist():
            x1, y1, x2, y2, confidence, class_id, belonging = row
            detections.append(
                (
                    [float(x1), float(y1), float(x2), float(y2)],
                    str(model.names[int(class_id)]),
                    int(belonging),
                    float(confidence),
                )
            )
    if not detections:
        return []
    box_tensor = torch.tensor([item[0] for item in detections], dtype=torch.float32)
    score_tensor = torch.tensor([item[3] for item in detections], dtype=torch.float32)
    keep = nms(box_tensor, score_tensor, nms_iou).tolist()
    return [
        TVRoyaleDetection(
            class_name=detections[index][1],
            belonging=detections[index][2],
            confidence=detections[index][3],
            x1=detections[index][0][0],
            y1=detections[index][0][1],
            x2=detections[index][0][2],
            y2=detections[index][0][3],
        )
        for index in keep
    ]


def _candidate_indices(
    parquet_path: Path,
    converter: TVRoyalePlacementConverter,
    *,
    max_rows: int | None,
) -> tuple[list[int], dict[str, int]]:
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    columns = ["card", "hand", "elixir", "x", "y", "offset"]
    table = pq.read_table(parquet_path, columns=columns)
    payload = table.to_pydict()
    candidates: list[int] = []
    skipped: Counter[str] = Counter()
    for index in range(table.num_rows):
        if int(payload["offset"][index]) != 0:
            skipped["offset_augmentation"] += 1
            continue
        accepted, reason = converter.is_location_training_candidate(
            raw_card=payload["card"][index],
            raw_hand=payload["hand"][index],
            elixir=float(payload["elixir"][index]),
            x=int(payload["x"][index]),
            y=int(payload["y"][index]),
        )
        if not accepted:
            assert reason is not None
            skipped[reason] += 1
            continue
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
    collected: list[dict[str, Any]] = []
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
            converted = converter.convert(
                raw_card=str(raw_row["card"]),
                raw_hand=raw_row["hand"],
                elixir=float(raw_row["elixir"]),
                frame=int(raw_row["frame"]),
                x=int(raw_row["x"]),
                y=int(raw_row["y"]),
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
                    "processed_candidates": min(source_index, max(selected) + 1),
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
        if source_index > max(selected):
            break
    flush()
    return collected


def _build_corpus(
    rows: list[dict[str, Any]],
    *,
    converter: TVRoyalePlacementConverter,
    source_path: Path,
    seed: int,
    label_source: str = "tv-royale-human-placement",
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    if not rows:
        raise ValueError("no TV Royale rows survived conversion")
    rows.sort(key=lambda item: (item["replay"], item["frame"], item["source_index"]))
    unique_rows: list[dict[str, Any]] = []
    seen_frame_actions: dict[tuple[str, int], int] = {}
    duplicate_source_rows = 0
    for item in rows:
        frame_key = (str(item["replay"]), int(item["frame"]))
        expert_action = int(item["converted"].expert_action)
        previous = seen_frame_actions.get(frame_key)
        if previous is not None:
            if previous != expert_action:
                raise ValueError(
                    "TV Royale source has conflicting labels for replay frame "
                    f"{frame_key}: {previous} versus {expert_action}"
                )
            duplicate_source_rows += 1
            continue
        seen_frame_actions[frame_key] = expert_action
        unique_rows.append(item)
    rows = unique_rows
    replay_names = sorted({str(item["replay"]) for item in rows})
    episode_by_replay = {name: index for index, name in enumerate(replay_names)}
    arrays: dict[str, list[Any]] = {
        "entity_ids": [],
        "entity_features": [],
        "entity_mask": [],
        "hand_ids": [],
        "global_features": [],
        "action_masks": [],
        "previous_actions": [],
        "previous_rewards": [],
        "episode_starts": [],
        "expert_actions": [],
        "episode_ids": [],
        "source_replays": [],
        "source_frames": [],
        "source_indices": [],
        "source_arenas": [],
    }
    previous_by_episode: dict[int, int] = {}
    card_counts: Counter[str] = Counter()
    arena_counts: Counter[str] = Counter()
    entity_counts: list[int] = []
    for item in rows:
        converted = item["converted"]
        episode_id = episode_by_replay[str(item["replay"])]
        episode_start = episode_id not in previous_by_episode
        previous_action = previous_by_episode.get(episode_id, converter.noop_action)
        for name in (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "hand_ids",
            "global_features",
        ):
            arrays[name].append(getattr(converted, name))
        arrays["action_masks"].append(converted.action_mask)
        arrays["previous_actions"].append(previous_action)
        arrays["previous_rewards"].append(0.0)
        arrays["episode_starts"].append(episode_start)
        arrays["expert_actions"].append(converted.expert_action)
        arrays["episode_ids"].append(episode_id)
        arrays["source_replays"].append(str(item["replay"]))
        arrays["source_frames"].append(int(item["frame"]))
        arrays["source_indices"].append(int(item["source_index"]))
        arrays["source_arenas"].append(str(item["arena"]))
        previous_by_episode[episode_id] = converted.expert_action
        card_counts[converted.target_card] += 1
        arena_counts[str(item["arena"])] += 1
        entity_counts.append(int(converted.entity_mask.sum()))

    samples = len(rows)
    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        seed=seed,
        decisions=samples,
        samples=samples,
        decision_interval=1,
        max_ticks=3000,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=converter.max_entities,
        token_names=converter.builder.token_names,
        reward_profile=DEFENSE_V2,
        workers=1,
        behavior_checkpoint=None,
        expert_probability=1.0,
        stable_root_candidates=False,
        behavior_opponent=None,
        label_source=label_source,
    )
    payload = {
        name: np.stack(values)
        for name, values in arrays.items()
        if name
        in {
            "entity_ids",
            "entity_features",
            "entity_mask",
            "hand_ids",
            "global_features",
            "action_masks",
        }
    }
    payload.update(
        {
            "previous_actions": np.asarray(arrays["previous_actions"], dtype=np.int64),
            "previous_rewards": np.asarray(arrays["previous_rewards"], dtype=np.float32),
            "episode_starts": np.asarray(arrays["episode_starts"], dtype=np.bool_),
            "expert_actions": np.asarray(arrays["expert_actions"], dtype=np.int64),
            "episode_ids": np.asarray(arrays["episode_ids"], dtype=np.int64),
            "source_replays": np.asarray(arrays["source_replays"], dtype=np.str_),
            "source_frames": np.asarray(arrays["source_frames"], dtype=np.int64),
            "source_indices": np.asarray(arrays["source_indices"], dtype=np.int64),
            "source_arenas": np.asarray(arrays["source_arenas"], dtype=np.str_),
            "metadata_json": np.asarray(metadata.to_json()),
        }
    )
    statistics = {
        "metadata": asdict(metadata),
        "source": str(source_path),
        "source_sha256": file_sha256(source_path),
        "episodes": len(replay_names),
        "samples": samples,
        "cards": dict(sorted(card_counts.items())),
        "arenas": dict(sorted(arena_counts.items())),
        "mean_detected_entities": float(np.mean(entity_counts)),
        "max_detected_entities": max(entity_counts),
        "duplicate_source_rows_removed": duplicate_source_rows,
    }
    return payload, statistics


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
        raise ValueError("source contains no supported located placement rows")
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
        rows, converter=converter, source_path=parquet_path, seed=args.seed
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
