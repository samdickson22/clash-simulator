from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np

from scripts.extract_tv_royale_youtube_fullmatch import (
    ARENA_REGION,
    CLOCK_REGION,
    HUD_ROIS,
    _atomic_json,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _frame(video: Path, timestamp_ms: int) -> np.ndarray:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp_ms / 1000.0:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    image = cv2.imdecode(np.frombuffer(result.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"could not decode audit frame at {timestamp_ms} ms")
    return cast(np.ndarray, image)


def _box(
    width: int, height: int, relative: tuple[float, float, float, float]
) -> tuple[int, int, int, int]:
    x, y, w, h = relative
    return (
        round(x * width),
        round(y * height),
        round((x + w) * width),
        round((y + h) * height),
    )


def _short_card(head: dict[str, Any]) -> str:
    value = head.get("value") or head.get("candidate") or "?"
    name = str(value).split(":", 1)[-1]
    return f"{name}{'' if head.get('valid') else '?'}"


def _render(image: np.ndarray, record: dict[str, Any], label: str) -> np.ndarray:
    output = image.copy()
    height, width = output.shape[:2]
    ax1, ay1, ax2, ay2 = _box(width, height, ARENA_REGION)
    arena_width = ax2 - ax1
    arena_height = ay2 - ay1
    grid_top = ay1 + round(arena_height * 62 / 683)
    grid_bottom = ay1 + round(arena_height * 676 / 683)
    for column in range(19):
        x = round(ax1 + arena_width * column / 18)
        cv2.line(output, (x, grid_top), (x, grid_bottom), (120, 210, 255), 1)
    for row in range(33):
        y = round(grid_bottom - (grid_bottom - grid_top) * row / 32)
        cv2.line(output, (ax1, y), (ax2, y), (120, 210, 255), 1)

    for entity in record["public"]["entities"]:
        if entity["world_position"] is None or not entity["identity"]["valid"]:
            continue
        x1, y1, x2, y2 = entity["sprite_box_normalized"]
        pixel_box = (
            round(ax1 + x1 * arena_width),
            round(ay1 + y1 * arena_height),
            round(ax1 + x2 * arena_width),
            round(ay1 + y2 * arena_height),
        )
        color = (255, 170, 40) if entity["team_id"] == 0 else (40, 80, 255)
        cv2.rectangle(output, pixel_box[:2], pixel_box[2:], color, 2)
        identity = str(entity["identity"]["stable_key"]).split(":", 1)[-1]
        hp = f" hp~{entity['hp_fraction']:.2f}" if entity["hp_valid"] else ""
        cv2.putText(
            output,
            identity + hp,
            (pixel_box[0], max(18, pixel_box[1] - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            color,
            1,
            cv2.LINE_AA,
        )

    for player_id in (0, 1):
        hud = record["offline_privileged_hud"][str(player_id)]
        color = (255, 190, 50) if player_id == 0 else (60, 100, 255)
        for slot, (relative, head) in enumerate(
            zip(HUD_ROIS[player_id]["hand"], hud["hand"], strict=True)
        ):
            x1, y1, x2, y2 = _box(width, height, relative)
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                output,
                f"P{player_id}s{slot} {_short_card(head)}",
                (x1, max(18, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.39,
                color,
                1,
                cv2.LINE_AA,
            )
        nx1, ny1, nx2, ny2 = _box(width, height, HUD_ROIS[player_id]["next"])
        cv2.rectangle(output, (nx1, ny1), (nx2, ny2), color, 2)
        cv2.putText(
            output,
            f"Next {_short_card(hud['next_card'])}",
            (nx1, max(18, ny1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.39,
            color,
            1,
            cv2.LINE_AA,
        )
        elixir = hud["elixir"]
        cv2.putText(
            output,
            f"P{player_id} elixir~{elixir.get('value') if elixir.get('valid') else '?'}",
            (12, 70 + 30 * player_id),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )

    cx1, cy1, cx2, cy2 = _box(width, height, CLOCK_REGION)
    cv2.rectangle(output, (cx1, cy1), (cx2, cy2), (255, 255, 255), 2)
    clock = record["public"]["clock"]
    cv2.putText(
        output,
        f"clock {clock.get('value') if clock.get('valid') else '?'}s c={clock.get('confidence', 0):.2f}",
        (cx1, max(18, cy1 - 5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    for event in record["offline_evidence"].get("play_events", []):
        if not event.get("placement_valid"):
            continue
        tile_x, tile_y = event["deployment_tile_absolute"]
        x1 = round(ax1 + arena_width * tile_x / 18)
        x2 = round(ax1 + arena_width * (tile_x + 1) / 18)
        y1 = round(grid_bottom - (grid_bottom - grid_top) * (tile_y + 1) / 32)
        y2 = round(grid_bottom - (grid_bottom - grid_top) * tile_y / 32)
        cv2.rectangle(output, (x1, y1), (x2, y2), (0, 255, 255), 5)
        cv2.putText(
            output,
            str(event.get("card_identity") or "untyped marker"),
            (x1, max(18, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

    cv2.rectangle(output, (0, 0), (width, 125), (15, 15, 15), -1)
    cv2.putText(
        output,
        label,
        (12, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        output,
        f"PTS {record['output_pts']} @ {record['timestamp_ms']}ms | boxes are sprites, never hitboxes",
        (12, 58),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        output,
        "18x32 grid maps visual centers only; collision/deployment footprints are data mechanics",
        (12, 88),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (120, 210, 255),
        1,
        cv2.LINE_AA,
    )
    return cast(np.ndarray, output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--neutral", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    with gzip.open(args.neutral, "rt", encoding="utf-8") as source:
        rows = [json.loads(line) for line in source if line.strip()]
    selections = [
        (300, "early 30s"),
        (330, "ambiguous selected-card frame"),
        (786, "player-0 complete interval"),
        (1600, "mid-match 160s"),
        (1778, "player-1 complete interval"),
        (3000, "late 300s"),
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    for pts, label in selections:
        record = rows[pts]
        image = _render(_frame(args.video, int(record["timestamp_ms"])), record, label)
        path = args.output_dir / f"audit_{pts:04d}.jpg"
        if not cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, 92]):
            raise ValueError(f"could not write {path}")
        rendered.append(
            {"pts": pts, "label": label, "path": str(path), "sha256": _sha256(path)}
        )
    cells = []
    for item in rendered:
        cell = cv2.imread(str(item["path"]))
        if cell is None:
            raise ValueError(f"could not reopen audit render {item['path']}")
        cells.append(cv2.resize(cell, (394, 853)))
    contact = np.vstack([np.hstack(cells[:3]), np.hstack(cells[3:])])
    contact_path = args.output_dir / "fullmatch_early_mid_late_ambiguous_contact.jpg"
    cv2.imwrite(str(contact_path), contact, [cv2.IMWRITE_JPEG_QUALITY, 92])
    manifest = {
        "schema": "clasher.youtube.fullmatch.visual_audit.v1",
        "video_sha256": _sha256(args.video),
        "neutral_sha256": _sha256(args.neutral),
        "renders": rendered,
        "contact": {"path": str(contact_path), "sha256": _sha256(contact_path)},
        "manual_review_required": True,
    }
    manifest_path = args.output_dir / "manifest.json"
    _atomic_json(manifest_path, manifest)
    print(
        json.dumps(
            {"manifest": str(manifest_path), "sha256": _sha256(manifest_path)}, indent=2
        )
    )


if __name__ == "__main__":
    main()
