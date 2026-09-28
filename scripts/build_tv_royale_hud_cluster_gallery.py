from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import gzip
import hashlib
import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import IO, Any, cast

import cv2
import numpy as np

from scripts.extract_tv_royale_youtube_fullmatch import (
    HUD_ROIS,
    _atomic_json,
    _crop_relative,
    _sha256,
    _vector,
)

SCHEMA = "clasher.youtube.hud_cluster_gallery.v1"


def _read_exact(stream: IO[bytes], size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _pixel_sha256(image: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest()


def _card_art_region(crop: np.ndarray) -> np.ndarray:
    height, width = crop.shape[:2]
    return crop[
        round(height * 0.05) : max(round(height * 0.72), 1),
        round(width * 0.08) : max(round(width * 0.92), 1),
    ]


def cosine_kmeans(
    vectors: np.ndarray, *, clusters: int, iterations: int = 50
) -> tuple[np.ndarray, np.ndarray]:
    if vectors.ndim != 2 or not len(vectors):
        raise ValueError("vectors must be a nonempty matrix")
    if not 1 <= clusters <= len(vectors):
        raise ValueError("clusters must be within the vector count")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    normalized = vectors / np.maximum(norms, 1e-12)
    first = int(np.argmin(np.sum(normalized, axis=1)))
    selected = [first]
    nearest = 1.0 - normalized @ normalized[first]
    while len(selected) < clusters:
        index = int(np.argmax(nearest))
        selected.append(index)
        nearest = np.minimum(nearest, 1.0 - normalized @ normalized[index])
    centroids = normalized[np.asarray(selected)].copy()
    assignments = np.full(len(normalized), -1, dtype=np.int32)
    for _ in range(iterations):
        updated = np.argmax(normalized @ centroids.T, axis=1).astype(np.int32)
        if np.array_equal(updated, assignments):
            break
        assignments = updated
        next_centroids = []
        for cluster in range(clusters):
            members = normalized[assignments == cluster]
            if not len(members):
                raise RuntimeError(f"cosine k-means produced empty cluster {cluster}")
            centroid = members.mean(axis=0)
            centroid /= max(float(np.linalg.norm(centroid)), 1e-12)
            next_centroids.append(centroid)
        centroids = np.asarray(next_centroids, dtype=np.float32)
    return assignments, centroids


def _representatives(
    *,
    vectors: np.ndarray,
    assignments: np.ndarray,
    centroids: np.ndarray,
    metadata: list[dict[str, int]],
    cluster: int,
    count: int = 6,
) -> list[int]:
    indices = np.flatnonzero(assignments == cluster)
    ranked = sorted(
        indices.tolist(),
        key=lambda index: (-float(vectors[index] @ centroids[cluster]), index),
    )
    selected: list[int] = []
    for index in ranked:
        frame = metadata[index]["sample_index"]
        if all(abs(frame - metadata[other]["sample_index"]) >= 4 for other in selected):
            selected.append(index)
        if len(selected) == count:
            return selected
    for index in ranked:
        if index not in selected:
            selected.append(index)
        if len(selected) == count:
            break
    return selected


def _render_gallery(
    *,
    crops: list[np.ndarray],
    metadata: list[dict[str, int]],
    assignments: np.ndarray,
    centroids: np.ndarray,
    vectors: np.ndarray,
    output: Path,
    representative_root: Path | None = None,
) -> list[dict[str, Any]]:
    rows: list[np.ndarray] = []
    clusters: list[dict[str, Any]] = []
    for player_id in (0, 1):
        player_indices = np.asarray(
            [index for index, row in enumerate(metadata) if row["player_id"] == player_id]
        )
        player_assignments = assignments[player_indices]
        for cluster in sorted(set(player_assignments.tolist())):
            global_indices = player_indices[player_assignments == cluster]
            local_vectors = vectors[global_indices]
            local_metadata = [metadata[index] for index in global_indices]
            local_assignments = np.zeros(len(global_indices), dtype=np.int32)
            local_centroid = centroids[cluster : cluster + 1]
            representative_local = _representatives(
                vectors=local_vectors,
                assignments=local_assignments,
                centroids=local_centroid,
                metadata=local_metadata,
                cluster=0,
            )
            representative_indices = [int(global_indices[index]) for index in representative_local]
            representative_rows: list[dict[str, Any]] = []
            for representative_index, index in enumerate(representative_indices):
                artifact: dict[str, Any] = {
                    **metadata[index],
                    "pixel_sha256": _pixel_sha256(crops[index]),
                }
                if representative_root is not None:
                    representative_root.mkdir(parents=True, exist_ok=True)
                    artifact_path = representative_root / (
                        f"p{player_id}_c{cluster:02d}_r{representative_index}_"
                        f"f{metadata[index]['sample_index']:04d}_"
                        f"s{metadata[index]['slot']}.png"
                    )
                    if not cv2.imwrite(str(artifact_path), crops[index]):
                        raise ValueError(
                            f"could not write representative crop {artifact_path}"
                        )
                    artifact["artifact_path"] = str(artifact_path)
                    artifact["artifact_sha256"] = _sha256(artifact_path)
                representative_rows.append(artifact)
            slots = Counter(metadata[index]["slot"] for index in global_indices)
            label = np.full((150, 250, 3), 20, dtype=np.uint8)
            cv2.putText(
                label,
                f"P{player_id} cluster {cluster}",
                (8, 34),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                label,
                f"n={len(global_indices)} slots={dict(sorted(slots.items()))}",
                (8, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (200, 230, 255),
                1,
                cv2.LINE_AA,
            )
            panels: list[np.ndarray] = [label]
            for index in representative_indices:
                panel = cv2.resize(crops[index], (110, 150), interpolation=cv2.INTER_AREA)
                cv2.rectangle(panel, (0, 0), (109, 25), (0, 0, 0), -1)
                cv2.putText(
                    panel,
                    f"f{metadata[index]['sample_index']} s{metadata[index]['slot']}",
                    (3, 18),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
                panels.append(panel)
            while len(panels) < 7:
                panels.append(np.zeros((150, 110, 3), dtype=np.uint8))
            rows.append(cast(np.ndarray, np.hstack(panels)))
            clusters.append(
                {
                    "player_id": player_id,
                    "cluster": int(cluster),
                    "observations": len(global_indices),
                    "slot_counts": {str(key): value for key, value in sorted(slots.items())},
                    "representatives": representative_rows,
                }
            )
    image = np.vstack(rows)
    if not cv2.imwrite(str(output), image, [cv2.IMWRITE_JPEG_QUALITY, 94]):
        raise ValueError(f"could not write gallery {output}")
    return clusters


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--neutral", type=Path, required=True)
    parser.add_argument("--sample-hz", type=int, default=2)
    parser.add_argument("--clusters-per-player", type=int, default=8)
    parser.add_argument("--minimum-candidate-score", type=float, default=0.0)
    parser.add_argument("--persist-representatives", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if (
        args.sample_hz <= 0
        or args.clusters_per_player <= 0
        or not 0.0 <= args.minimum_candidate_score <= 1.0
    ):
        raise ValueError("invalid sample rate, cluster count, or candidate-score floor")
    started = time.perf_counter()
    acquisition = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    duration = float(acquisition["source_media"]["probed_duration_seconds"])
    expected_frames = round(duration * args.sample_hz)
    with gzip.open(args.neutral, "rt", encoding="utf-8") as source:
        neutral = [json.loads(line) for line in source if line.strip()]
    neutral_hz = int(str(acquisition["decode"]["output_time_base"]).split("/", 1)[1])
    if neutral_hz % args.sample_hz:
        raise ValueError("neutral cadence must be an integer multiple of gallery cadence")
    neutral_stride = neutral_hz // args.sample_hz
    if len(neutral) != int(acquisition["decode"]["sample_count"]):
        raise ValueError("neutral rows do not match the acquisition sample count")
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(args.video.resolve()),
            "-vf",
            f"fps={args.sample_hz},scale=591:1280:flags=lanczos",
            "-pix_fmt",
            "bgr24",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    frame_bytes = 591 * 1280 * 3
    crops: list[np.ndarray] = []
    metadata: list[dict[str, int]] = []
    frame_index = 0
    while True:
        raw = _read_exact(process.stdout, frame_bytes)
        if not raw:
            break
        if len(raw) != frame_bytes:
            raise ValueError(f"short decoded frame {frame_index}")
        frame = np.frombuffer(raw, dtype=np.uint8).reshape(1280, 591, 3)
        neutral_index = min(frame_index * neutral_stride, len(neutral) - 1)
        record = neutral[neutral_index]
        for player_id in (0, 1):
            hud = record["offline_privileged_hud"][str(player_id)]
            if not hud["elixir"]["valid"]:
                continue
            layout = HUD_ROIS[player_id]
            boxes = [*layout["hand"], layout["next"]]
            heads = [*hud["hand"], hud["next_card"]]
            for slot, (box, head) in enumerate(zip(boxes, heads, strict=True)):
                if head.get("candidate") == "empty" or float(
                    head.get("score", 0.0)
                ) < args.minimum_candidate_score:
                    continue
                crop = _crop_relative(frame, box)
                crops.append(np.ascontiguousarray(crop))
                metadata.append(
                    {
                        "player_id": player_id,
                        "slot": slot,
                        "sample_index": frame_index,
                        "timestamp_ms": round(frame_index * 1000 / args.sample_hz),
                    }
                )
        frame_index += 1
    process.stdout.close()
    stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
    if process.wait() != 0:
        raise RuntimeError(f"ffmpeg decode failed: {stderr[-1000:]}")
    if frame_index != expected_frames:
        raise ValueError(f"decoded {frame_index} frames, expected {expected_frames}")
    vectors = np.stack(
        [_vector(_card_art_region(crop), (32, 32)) for crop in crops], axis=0
    )

    assignments = np.empty(len(vectors), dtype=np.int32)
    centroids = np.empty((args.clusters_per_player * 2, vectors.shape[1]), dtype=np.float32)
    for player_id in (0, 1):
        indices = np.asarray(
            [index for index, row in enumerate(metadata) if row["player_id"] == player_id]
        )
        local_assignments, local_centroids = cosine_kmeans(
            vectors[indices], clusters=args.clusters_per_player
        )
        assignments[indices] = local_assignments + player_id * args.clusters_per_player
        centroids[
            player_id * args.clusters_per_player : (player_id + 1)
            * args.clusters_per_player
        ] = local_centroids

    args.output_dir.mkdir(parents=True, exist_ok=True)
    arrays_path = args.output_dir / "hud_clusters.npz"
    np.savez_compressed(
        arrays_path,
        embeddings=vectors.astype(np.float16),
        assignments=assignments,
        centroids=centroids.astype(np.float16),
        player_ids=np.asarray([row["player_id"] for row in metadata], dtype=np.int8),
        slots=np.asarray([row["slot"] for row in metadata], dtype=np.int8),
        sample_indices=np.asarray(
            [row["sample_index"] for row in metadata], dtype=np.int32
        ),
    )
    gallery_path = args.output_dir / "hud_cluster_gallery.jpg"
    cluster_rows = _render_gallery(
        crops=crops,
        metadata=metadata,
        assignments=assignments,
        centroids=centroids,
        vectors=vectors,
        output=gallery_path,
        representative_root=(
            args.output_dir / "representatives"
            if args.persist_representatives
            else None
        ),
    )
    manifest = {
        "schema": SCHEMA,
        "video": str(args.video.resolve()),
        "video_sha256": _sha256(args.video),
        "source_manifest": str(args.source_manifest.resolve()),
        "source_manifest_sha256": _sha256(args.source_manifest),
        "neutral": str(args.neutral.resolve()),
        "neutral_sha256": _sha256(args.neutral),
        "feature_contract": (
            "32x32 interior-art spatial LAB mean-centered L2-normalized pixels; "
            "cost badge, border tail, and Next text excluded"
        ),
        "sample_hz": args.sample_hz,
        "sampled_frames": frame_index,
        "crop_observations": len(crops),
        "clusters_per_player": args.clusters_per_player,
        "minimum_candidate_score": args.minimum_candidate_score,
        "representatives_persisted": args.persist_representatives,
        "clusters": cluster_rows,
        "artifacts": {
            "arrays": {"path": str(arrays_path), "sha256": _sha256(arrays_path)},
            "gallery": {"path": str(gallery_path), "sha256": _sha256(gallery_path)},
        },
        "timing_seconds": time.perf_counter() - started,
        "status": "unlabeled_active_learning_gallery",
    }
    manifest_path = args.output_dir / "manifest.json"
    _atomic_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "sha256": _sha256(manifest_path),
                "frames": frame_index,
                "crops": len(crops),
                "clusters": len(cluster_rows),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
