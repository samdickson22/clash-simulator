from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import IO, Any, cast

import numpy as np

from scripts.build_tv_royale_hud_cluster_gallery import _card_art_region
from scripts.extract_tv_royale_youtube_fullmatch import (
    HUD_ROIS,
    _atomic_json,
    _crop_relative,
    _sha256,
    _vector,
)

SCHEMA = "clasher.youtube.hud_cluster_action_join.v1"


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


def _mode(values: list[tuple[int, float]]) -> tuple[int, float]:
    if not values:
        raise ValueError("cluster mode has no observations")
    counts = Counter(cluster for cluster, _score in values)
    best_count = max(counts.values())
    candidates = {cluster for cluster, count in counts.items() if count == best_count}
    selected = max(
        candidates,
        key=lambda cluster: (
            sum(score for value, score in values if value == cluster),
            -cluster,
        ),
    )
    scores = [score for cluster, score in values if cluster == selected]
    return selected, float(sum(scores) / len(scores))


def select_cycle_transition(
    before: list[int], after: list[int]
) -> tuple[int, str] | None:
    if len(before) != 5 or len(after) != 5:
        raise ValueError("cycle transition requires four hand slots and Next")
    changed = [slot for slot in range(4) if before[slot] != after[slot]]
    next_enters = [slot for slot in changed if after[slot] == before[4]]
    if len(next_enters) == 1:
        return next_enters[0], "unique_next_enters_changed_slot"
    if len(changed) == 1:
        return changed[0], "unique_changed_slot_without_next_confirmation"
    return None


def _decode_selected_frames(
    *, video: Path, sample_hz: int, selected: set[int]
) -> dict[int, np.ndarray]:
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            f"fps={sample_hz},scale=591:1280:flags=lanczos",
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
    output: dict[int, np.ndarray] = {}
    frame_index = 0
    while True:
        raw = _read_exact(process.stdout, frame_bytes)
        if not raw:
            break
        if len(raw) != frame_bytes:
            raise ValueError(f"short frame {frame_index}")
        if frame_index in selected:
            output[frame_index] = np.frombuffer(raw, dtype=np.uint8).reshape(
                1280, 591, 3
            ).copy()
        frame_index += 1
    process.stdout.close()
    stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
    if process.wait() != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr[-1000:]}")
    missing = sorted(selected.difference(output))
    if missing:
        raise ValueError(f"video ended before selected frames: {missing[:10]}")
    return output


def _slot_clusters(
    *,
    frame: np.ndarray,
    player_id: int,
    centroids: np.ndarray,
    clusters_per_player: int,
) -> list[tuple[int, float]]:
    layout = HUD_ROIS[player_id]
    boxes = [*layout["hand"], layout["next"]]
    first = player_id * clusters_per_player
    player_centroids = centroids[first : first + clusters_per_player]
    output = []
    for box in boxes:
        crop = _crop_relative(frame, box)
        vector = _vector(_card_art_region(crop), (32, 32))
        scores = vector @ player_centroids.T
        local = int(np.argmax(scores))
        output.append((first + local, float(scores[local])))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--cluster-manifest", type=Path, required=True)
    parser.add_argument("--cluster-arrays", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--identity-map", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context-start-frames", type=int, default=5)
    parser.add_argument("--context-end-frames", type=int, default=2)
    args = parser.parse_args()
    if args.context_start_frames < args.context_end_frames or args.context_end_frames <= 0:
        raise ValueError("context frames must satisfy start >= end > 0")
    source = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    sample_hz = int(str(source["decode"]["output_time_base"]).split("/", 1)[1])
    cluster_manifest = json.loads(args.cluster_manifest.read_text(encoding="utf-8"))
    if cluster_manifest.get("schema") != "clasher.youtube.hud_cluster_gallery.v1":
        raise ValueError("unsupported cluster manifest")
    clusters_per_player = int(cluster_manifest["clusters_per_player"])
    arrays = np.load(args.cluster_arrays)
    centroids = np.asarray(arrays["centroids"], dtype=np.float32)
    centroids /= np.maximum(np.linalg.norm(centroids, axis=1, keepdims=True), 1e-12)
    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    approved_identities: dict[tuple[int, int], str] = {}
    if args.identity_map is not None:
        identity_map = json.loads(args.identity_map.read_text(encoding="utf-8"))
        if identity_map.get("schema") != "clasher.youtube.reviewed_cluster_identities.v1":
            raise ValueError("unsupported cluster identity map")
        if identity_map.get("cluster_manifest_sha256") != _sha256(
            args.cluster_manifest
        ) or identity_map.get("cluster_arrays_sha256") != _sha256(args.cluster_arrays):
            raise ValueError("cluster identity map does not bind the supplied gallery")
        for row in identity_map["identities"]:
            key = (int(row["player_id"]), int(row["cluster"]))
            if key in approved_identities:
                raise ValueError(f"duplicate reviewed cluster identity {key}")
            approved_identities[key] = str(row["identity"])
    labels = list(gold["labels"])
    offsets = list(
        range(-args.context_start_frames, -args.context_end_frames + 1)
    ) + list(range(args.context_end_frames, args.context_start_frames + 1))
    selected_frames = {
        max(0, round(int(label["timestamp_ms"]) * sample_hz / 1000) + offset)
        for label in labels
        for offset in offsets
    }
    frames = _decode_selected_frames(
        video=args.video.resolve(), sample_hz=sample_hz, selected=selected_frames
    )

    output_rows: list[dict[str, Any]] = []
    label_votes: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)
    for label in labels:
        player_id = int(label["player_id"])
        event_frame = round(int(label["timestamp_ms"]) * sample_hz / 1000)
        before_rows = [
            _slot_clusters(
                frame=frames[max(0, event_frame + offset)],
                player_id=player_id,
                centroids=centroids,
                clusters_per_player=clusters_per_player,
            )
            for offset in offsets
            if offset < 0
        ]
        after_rows = [
            _slot_clusters(
                frame=frames[event_frame + offset],
                player_id=player_id,
                centroids=centroids,
                clusters_per_player=clusters_per_player,
            )
            for offset in offsets
            if offset > 0
        ]
        before = [
            _mode([row[slot] for row in before_rows]) for slot in range(5)
        ]
        after = [_mode([row[slot] for row in after_rows]) for slot in range(5)]
        transition = select_cycle_transition(
            [cluster for cluster, _score in before],
            [cluster for cluster, _score in after],
        )
        selected_cluster = None if transition is None else before[transition[0]][0]
        predicted_identity = (
            None
            if selected_cluster is None
            else approved_identities.get((player_id, selected_cluster))
        )
        if (
            label.get("play_valid")
            and label.get("identity_valid")
            and selected_cluster is not None
        ):
            label_votes[(player_id, selected_cluster)][str(label["card_identity"])] += 1
        output_rows.append(
            {
                "label_id": label["label_id"],
                "player_id": player_id,
                "timestamp_ms": label["timestamp_ms"],
                "gold_play_valid": bool(label.get("play_valid")),
                "gold_identity": label.get("card_identity"),
                "before": [
                    {"cluster": cluster, "mean_similarity": score}
                    for cluster, score in before
                ],
                "after": [
                    {"cluster": cluster, "mean_similarity": score}
                    for cluster, score in after
                ],
                "selected_slot": None if transition is None else transition[0],
                "selected_cluster": selected_cluster,
                "predicted_identity": predicted_identity,
                "predicted_identity_valid": predicted_identity is not None,
                "transition_evidence": None if transition is None else transition[1],
            }
        )
    conflicts = []
    suggestions = []
    for (player_id, cluster), votes in sorted(label_votes.items()):
        if len(votes) > 1:
            conflicts.append(
                {"player_id": player_id, "cluster": cluster, "votes": dict(votes)}
            )
        identity, count = votes.most_common(1)[0]
        suggestions.append(
            {
                "player_id": player_id,
                "cluster": cluster,
                "identity": identity,
                "votes": count,
                "all_votes": dict(votes),
                "conflict": len(votes) > 1,
            }
        )
    real_plays = [row for row in output_rows if row["gold_play_valid"]]
    real_identity_predictions = [
        row for row in real_plays if row["predicted_identity_valid"]
    ]
    payload = {
        "schema": SCHEMA,
        "video_sha256": _sha256(args.video),
        "source_manifest_sha256": _sha256(args.source_manifest),
        "cluster_manifest_sha256": _sha256(args.cluster_manifest),
        "cluster_arrays_sha256": _sha256(args.cluster_arrays),
        "gold_sha256": _sha256(args.gold),
        "identity_map_sha256": (
            None if args.identity_map is None else _sha256(args.identity_map)
        ),
        "sample_hz": sample_hz,
        "context_offsets_frames": offsets,
        "rows": output_rows,
        "cluster_identity_suggestions": suggestions,
        "conflicts": conflicts,
        "counts": {
            "gold_rows": len(labels),
            "gold_real_plays": len(real_plays),
            "real_plays_with_unique_cycle_transition": sum(
                row["selected_cluster"] is not None for row in real_plays
            ),
            "false_plays_with_transition": sum(
                row["selected_cluster"] is not None
                for row in output_rows
                if not row["gold_play_valid"]
            ),
            "suggested_cluster_identities": len(suggestions),
            "conflicts": len(conflicts),
            "real_play_identity_predictions": len(real_identity_predictions),
            "real_play_identity_correct": sum(
                row["predicted_identity"] == row["gold_identity"]
                for row in real_identity_predictions
            ),
            "false_play_identity_predictions": sum(
                row["predicted_identity_valid"]
                for row in output_rows
                if not row["gold_play_valid"]
            ),
        },
    }
    _atomic_json(args.output, payload)
    counts = cast(dict[str, int], payload["counts"])
    print(json.dumps({"output": str(args.output), **counts}, indent=2))


if __name__ == "__main__":
    main()
