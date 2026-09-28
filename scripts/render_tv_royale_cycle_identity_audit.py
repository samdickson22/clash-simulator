from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import IO, Any

import cv2
import numpy as np

from scripts.extract_tv_royale_youtube_fullmatch import (
    HUD_ROIS,
    _atomic_json,
    _crop_relative,
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


def render_identity_sheet(
    *, video: Path, labels: list[dict[str, Any]], output: Path
) -> None:
    by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in labels:
        by_frame[max(0, round((int(row["timestamp_ms"]) - 500) / 100))].append(row)
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            "fps=10,scale=591:1280:flags=lanczos",
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
    cells: list[np.ndarray] = []
    frame_index = 0
    while True:
        raw = _read_exact(process.stdout, frame_bytes)
        if not raw:
            break
        if len(raw) != frame_bytes:
            raise ValueError(f"short frame {frame_index}")
        if frame_index in by_frame:
            frame = np.frombuffer(raw, dtype=np.uint8).reshape(1280, 591, 3)
            for row in by_frame[frame_index]:
                box = HUD_ROIS[int(row["player_id"])]["hand"][
                    int(row["selected_slot"])
                ]
                crop = _crop_relative(frame, box)
                art = cv2.resize(crop, (180, 235), interpolation=cv2.INTER_CUBIC)
                cell = np.full((310, 220, 3), 20, np.uint8)
                cell[8:243, 20:200] = art
                identity = str(row["card_identity"]).split(":", 1)[-1]
                cv2.putText(
                    cell,
                    identity[:22],
                    (8, 268),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.52,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    cell,
                    f"P{row['player_id']} {row['timestamp_ms']/1000:.1f}s drop {row['observed_elixir_drop']:.1f}",
                    (8, 294),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (120, 220, 255),
                    1,
                    cv2.LINE_AA,
                )
                cells.append(cell)
        frame_index += 1
    process.stdout.close()
    stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
    if process.wait() != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr[-1000:]}")
    if len(cells) != len(labels):
        raise ValueError(f"rendered {len(cells)} of {len(labels)} labels")
    columns = 4
    while len(cells) % columns:
        cells.append(np.zeros_like(cells[0]))
    sheet = np.vstack(
        [np.hstack(cells[index : index + columns]) for index in range(0, len(cells), columns)]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), sheet, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        raise ValueError(f"could not write {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    labels = list(selection["labels"])
    render_identity_sheet(video=args.video, labels=labels, output=args.output)
    manifest = {
        "schema": "clasher.youtube.cycle_identity_visual_audit.v1",
        "video_sha256": _sha256(args.video),
        "selection_sha256": _sha256(args.selection),
        "image": {"path": str(args.output), "sha256": _sha256(args.output)},
        "labels": len(labels),
    }
    manifest_path = args.output.with_suffix(".json")
    _atomic_json(manifest_path, manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
