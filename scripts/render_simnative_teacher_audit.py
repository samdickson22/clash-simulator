# mypy: disable-error-code="import-untyped"
"""Render grid-registered audits for simulator-native teacher trajectories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from clasher.arena import TileGrid
from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES


def _point(x: float, y: float, scale: int, margin: int) -> tuple[int, int]:
    return margin + round(x * scale), margin + round((BOARD_HEIGHT - y) * scale)


def render_audits(corpus: Path, output_dir: Path, *, samples: int) -> list[Path]:
    if samples <= 0:
        raise ValueError("samples must be positive")
    with np.load(corpus, allow_pickle=False) as payload:
        arrays = {name: payload[name].copy() for name in payload.files}
    metadata = json.loads(str(arrays["metadata_json"].item()))
    token_names = tuple(metadata["token_names"])
    actions = np.asarray(arrays["expert_actions"], dtype=np.int64)
    play_rows = np.flatnonzero(actions < NUM_HAND_SLOTS * NUM_TILES)
    if not len(play_rows):
        raise ValueError("corpus has no placement rows to render")
    chosen = play_rows[
        np.linspace(0, len(play_rows) - 1, min(samples, len(play_rows)), dtype=np.int64)
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    scale = 32
    margin = 40
    sidebar = 330
    width = BOARD_WIDTH * scale + 2 * margin + sidebar
    height = BOARD_HEIGHT * scale + 2 * margin
    outputs: list[Path] = []
    for audit_index, row in enumerate(chosen.tolist()):
        image = np.full((height, width, 3), (32, 32, 36), dtype=np.uint8)
        arena_right = margin + BOARD_WIDTH * scale
        arena_bottom = margin + BOARD_HEIGHT * scale
        cv2.rectangle(
            image,
            (margin, margin),
            (arena_right, arena_bottom),
            (70, 64, 54),
            -1,
        )
        for x in range(BOARD_WIDTH + 1):
            px = margin + x * scale
            cv2.line(image, (px, margin), (px, arena_bottom), (105, 100, 92), 1)
        for y in range(BOARD_HEIGHT + 1):
            py = margin + y * scale
            color = (0, 220, 255) if y == BOARD_HEIGHT // 2 else (105, 100, 92)
            cv2.line(image, (margin, py), (arena_right, py), color, 2 if y == 16 else 1)
        for x, y in TileGrid.BLOCKED_TILES:
            top_left = _point(float(x), float(y + 1), scale, margin)
            bottom_right = _point(float(x + 1), float(y), scale, margin)
            cv2.rectangle(image, top_left, bottom_right, (50, 50, 50), -1)

        action = int(actions[row])
        slot = action // NUM_TILES
        tile = action % NUM_TILES
        tile_x = tile % BOARD_WIDTH
        tile_y = tile // BOARD_WIDTH
        top_left = _point(float(tile_x), float(tile_y + 1), scale, margin)
        bottom_right = _point(float(tile_x + 1), float(tile_y), scale, margin)
        overlay = image.copy()
        cv2.rectangle(overlay, top_left, bottom_right, (40, 210, 80), -1)
        cv2.addWeighted(overlay, 0.52, image, 0.48, 0.0, image)
        center = _point(tile_x + 0.5, tile_y + 0.5, scale, margin)
        cv2.drawMarker(image, center, (90, 255, 120), cv2.MARKER_CROSS, 24, 3)

        valid = np.asarray(arrays["entity_mask"])[row]
        entity_ids = np.asarray(arrays["entity_ids"])[row]
        features = np.asarray(arrays["entity_features"])[row]
        for entity_id, feature in zip(entity_ids[valid], features[valid], strict=True):
            x = float(feature[0]) * BOARD_WIDTH
            y = float(feature[1]) * BOARD_HEIGHT
            point = _point(x, y, scale, margin)
            color = (255, 145, 45) if feature[2] > 0.5 else (55, 95, 255)
            radius = max(5, round(float(feature[26]) * 3.0 * scale))
            if feature[5] > 0.5:
                cv2.rectangle(
                    image,
                    (point[0] - radius, point[1] - radius),
                    (point[0] + radius, point[1] + radius),
                    color,
                    2,
                )
            else:
                cv2.circle(image, point, radius, color, 2)
            label = token_names[int(entity_id)][:13]
            cv2.putText(
                image,
                label,
                (point[0] + 4, point[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.30,
                color,
                1,
                cv2.LINE_AA,
            )

        hand_ids = np.asarray(arrays["hand_ids"])[row]
        card = token_names[int(hand_ids[slot])]
        replay = str(np.asarray(arrays["source_replays"])[row])
        source_frame = int(np.asarray(arrays["source_frames"])[row])
        lines = [
            "SIM-NATIVE TEACHER AUDIT",
            f"row {row}  audit {audit_index + 1}/{len(chosen)}",
            f"card: {card}",
            f"slot: {slot}  tile: ({tile_x}, {tile_y})",
            f"source frame: {source_frame}",
            f"replay: {replay[:18]}",
            "",
            "blue = human/own",
            "red = opponent",
            "square = building",
            "circle = other entity",
            "green = generated legal tile",
            "yellow = river boundary",
            "",
            "This validates simulator geometry.",
            "It does not claim the generated",
            "board matches the source video.",
        ]
        x_text = arena_right + 24
        for line_index, line in enumerate(lines):
            cv2.putText(
                image,
                line,
                (x_text, 62 + line_index * 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.47,
                (225, 225, 225),
                1,
                cv2.LINE_AA,
            )
        destination = output_dir / f"audit_{audit_index:03d}_row_{row:05d}.png"
        cv2.imwrite(str(destination), image)
        outputs.append(destination)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=12)
    args = parser.parse_args()
    outputs = render_audits(args.corpus, args.output_dir, samples=args.samples)
    print(json.dumps({"outputs": [str(path.resolve()) for path in outputs]}))


if __name__ == "__main__":
    main()
