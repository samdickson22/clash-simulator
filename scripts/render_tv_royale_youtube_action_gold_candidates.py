from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import IO

import cv2
import numpy as np

from scripts.extract_tv_royale_youtube_fullmatch import (
    ARENA_REGION,
    HUD_ROIS,
    _atomic_json,
    _sha256,
)


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


def _box(
    width: int, height: int, relative: tuple[float, float, float, float]
) -> tuple[int, int, int, int]:
    x, y, box_width, box_height = relative
    return (
        round(x * width),
        round(y * height),
        round((x + box_width) * width),
        round((y + box_height) * height),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.labels.read_text())
    labels = payload["labels"]
    by_frame = defaultdict(list)
    for label in labels:
        by_frame[round(int(label["timestamp_ms"]) / 100)].append(label)
    if not by_frame:
        raise ValueError("action candidate payload has no labels")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    decoder = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(args.video),
            "-vf",
            "fps=10,scale=591:1280:flags=lanczos",
            "-pix_fmt",
            "bgr24",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
    )
    assert decoder.stdout is not None
    frame_bytes = 591 * 1280 * 3
    rendered: list[tuple[str, np.ndarray]] = []
    individual_frames: list[dict[str, str]] = []
    context_offsets = (-3, 0, 3)
    context_indices = {
        max(0, label_frame + offset)
        for label_frame in by_frame
        for offset in context_offsets
    }
    context_frames: dict[int, np.ndarray] = {}
    annotated_frames: dict[str, tuple[int, np.ndarray]] = {}
    frame = 0
    seen_label_frames: set[int] = set()
    while True:
        raw = _read_exact(decoder.stdout, frame_bytes)
        if not raw:
            break
        if len(raw) != frame_bytes:
            raise ValueError(f"short frame {frame}: {len(raw)} of {frame_bytes} bytes")
        if frame not in by_frame and frame not in context_indices:
            frame += 1
            continue
        source = np.frombuffer(raw, dtype=np.uint8).reshape(1280, 591, 3)
        if frame in context_indices:
            context_frames[frame] = source.copy()
        if frame not in by_frame:
            frame += 1
            continue
        seen_label_frames.add(frame)
        for label in by_frame[frame]:
            image = source.copy()
            height, width = image.shape[:2]
            player = int(label["player_id"])
            color = (255, 180, 30) if player == 0 else (30, 80, 255)
            cv2.rectangle(image, (0, 0), (width, 115), (10, 10, 10), -1)
            identity = label.get("card_identity") or "identity?"
            cv2.putText(
                image,
                f"{label['label_id']} P{player} t={label['timestamp_ms']} drop={label['observed_elixir_drop']:.2f}",
                (8, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                image,
                f"prediction {identity} | tile {label.get('deployment_tile_absolute')}",
                (8, 55),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                color,
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                image,
                "MANUAL GOLD: accept/reject play; correct identity/tile; ? when not visible",
                (8, 83),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )
            for slot, relative in enumerate(HUD_ROIS[player]["hand"]):
                x1, y1, x2, y2 = _box(width, height, relative)
                cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    image,
                    str(slot),
                    (x1 + 2, y1 + 17),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    color,
                    2,
                    cv2.LINE_AA,
                )
            tile = label.get("deployment_tile_absolute")
            if isinstance(tile, list) and len(tile) == 2:
                ax1, ay1, ax2, ay2 = _box(width, height, ARENA_REGION)
                grid_top = ay1 + round((ay2 - ay1) * 62 / 683)
                grid_bottom = ay1 + round((ay2 - ay1) * 676 / 683)
                tx, ty = int(tile[0]), int(tile[1])
                x1 = round(ax1 + (ax2 - ax1) * tx / 18)
                x2 = round(ax1 + (ax2 - ax1) * (tx + 1) / 18)
                y1 = round(grid_bottom - (grid_bottom - grid_top) * (ty + 1) / 32)
                y2 = round(grid_bottom - (grid_bottom - grid_top) * ty / 32)
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 255), 5)
            label_id = str(label["label_id"])
            safe_label = "".join(
                character if character.isalnum() or character in "-_" else "_"
                for character in label_id
            )
            individual_path = (
                args.output_dir
                / f"candidate_{len(rendered):03d}_{safe_label}.jpg"
            )
            if not cv2.imwrite(
                str(individual_path), image, [cv2.IMWRITE_JPEG_QUALITY, 94]
            ):
                raise ValueError(f"could not write candidate frame {individual_path}")
            individual_frames.append(
                {
                    "label_id": label_id,
                    "path": str(individual_path),
                    "sha256": _sha256(individual_path),
                }
            )
            annotated_frames[label_id] = (frame, image.copy())
            cell = cv2.resize(image, (296, 640), interpolation=cv2.INTER_AREA)
            rendered.append((label_id, cell))
        frame += 1
    decoder.stdout.close()
    if decoder.wait() != 0:
        raise ValueError("ffmpeg failed")
    missing_label_frames = sorted(set(by_frame).difference(seen_label_frames))
    if missing_label_frames:
        raise ValueError(f"video ended before labeled frames: {missing_label_frames[:10]}")

    temporal_frames: list[dict[str, str]] = []
    for label_id, (label_frame, annotated) in annotated_frames.items():
        panels: list[np.ndarray] = []
        for offset in context_offsets:
            if offset == 0:
                panel = annotated.copy()
            else:
                context_frame = max(0, label_frame + offset)
                if context_frame not in context_frames:
                    raise ValueError(f"missing temporal context frame {context_frame}")
                panel = context_frames[context_frame].copy()
                cv2.rectangle(panel, (0, 0), (panel.shape[1], 48), (10, 10, 10), -1)
                cv2.putText(
                    panel,
                    f"{offset * 100:+d} ms from {label_id}",
                    (8, 31),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
            panels.append(cv2.resize(panel, (296, 640), interpolation=cv2.INTER_AREA))
        safe_label = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in label_id
        )
        temporal_path = (
            args.output_dir
            / f"temporal_{len(temporal_frames):03d}_{safe_label}.jpg"
        )
        if not cv2.imwrite(
            str(temporal_path),
            np.hstack(panels),
            [cv2.IMWRITE_JPEG_QUALITY, 94],
        ):
            raise ValueError(f"could not write temporal frame {temporal_path}")
        temporal_frames.append(
            {
                "label_id": label_id,
                "path": str(temporal_path),
                "sha256": _sha256(temporal_path),
            }
        )

    sheets = []
    per_sheet = 12
    for sheet_index in range(0, len(rendered), per_sheet):
        cells = [item[1] for item in rendered[sheet_index : sheet_index + per_sheet]]
        while len(cells) < per_sheet:
            cells.append(np.zeros_like(cells[0]))
        sheet = np.vstack(
            [np.hstack(cells[row : row + 4]) for row in range(0, per_sheet, 4)]
        )
        path = args.output_dir / f"action_gold_sheet_{sheet_index // per_sheet:02d}.jpg"
        cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
        sheets.append({"path": str(path), "sha256": _sha256(path)})
    manifest = {
        "schema": "clasher.youtube.action_gold_visual_candidates.v1",
        "video_sha256": _sha256(args.video),
        "labels_sha256": _sha256(args.labels),
        "candidate_count": len(rendered),
        "individual_frames": individual_frames,
        "temporal_frames": temporal_frames,
        "sheets": sheets,
    }
    path = args.output_dir / "manifest.json"
    _atomic_json(path, manifest)
    print(
        json.dumps(
            {"manifest": str(path), "sha256": _sha256(path), "sheets": len(sheets)},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
