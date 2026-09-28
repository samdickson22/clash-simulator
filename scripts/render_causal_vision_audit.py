from __future__ import annotations

# mypy: disable-error-code="import-not-found,import-untyped"
import argparse
import io
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pyarrow.parquet as pq
from PIL import Image

from clasher.rl.tv_royale_replay import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    Y_OFFSET_BOTTOM,
    Y_OFFSET_TOP,
)

RAW_CROP_LEFT = 57
RAW_CROP_TOP = 137


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the exact confidence-aware tensors seen by the actor."
    )
    parser.add_argument("--input-parquet", required=True)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--public-sidecar", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--columns", type=int, default=4)
    return parser.parse_args()


def _token_names(corpus: np.lib.npyio.NpzFile) -> tuple[str, ...]:
    metadata = json.loads(str(corpus["metadata_json"].item()))
    names = metadata.get("token_names")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise ValueError("corpus metadata has no token_names")
    return tuple(names)


def _selected_indices(total: int, samples: int) -> np.ndarray:
    if total <= 0 or samples <= 0:
        return np.zeros((0,), dtype=np.int64)
    return np.unique(
        np.linspace(0, total - 1, min(total, samples), dtype=np.int64)
    )


def _decode_selected(path: Path, frames: set[int]) -> dict[int, np.ndarray]:
    result: dict[int, np.ndarray] = {}
    row = 0
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(columns=["image"], batch_size=64, use_threads=False):
        for value in batch.column(0):
            if row in frames:
                raw = value.as_py()["bytes"]
                full = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"))[..., ::-1]
                result[row] = full[
                    RAW_CROP_TOP : RAW_CROP_TOP + IMAGE_HEIGHT,
                    RAW_CROP_LEFT : RAW_CROP_LEFT + IMAGE_WIDTH,
                ].copy()
            row += 1
    missing = frames.difference(result)
    if missing:
        raise ValueError(f"raw replay is missing selected frames: {sorted(missing)[:10]}")
    return result


def _source_pixel(x: float, y: float) -> tuple[int, int]:
    grid_height = IMAGE_HEIGHT - Y_OFFSET_TOP - Y_OFFSET_BOTTOM
    return (
        round((1.0 - x) * IMAGE_WIDTH),
        round(Y_OFFSET_TOP + (1.0 - y) * grid_height),
    )


def _draw_grid(image: np.ndarray) -> None:
    grid_height = IMAGE_HEIGHT - Y_OFFSET_TOP - Y_OFFSET_BOTTOM
    for column in range(19):
        x = round(column * IMAGE_WIDTH / 18)
        cv2.line(image, (x, Y_OFFSET_TOP), (x, IMAGE_HEIGHT - Y_OFFSET_BOTTOM), (85, 85, 85), 1)
    for row in range(33):
        y = round(Y_OFFSET_TOP + row * grid_height / 32)
        cv2.line(image, (0, y), (IMAGE_WIDTH, y), (85, 85, 85), 1)
    river = round(Y_OFFSET_TOP + 16 * grid_height / 32)
    cv2.line(image, (0, river), (IMAGE_WIDTH, river), (0, 255, 255), 2)


def _render_row(
    image: np.ndarray,
    *,
    frame: int,
    ids: np.ndarray,
    features: np.ndarray,
    mask: np.ndarray,
    id_confidence: np.ndarray,
    feature_confidence: np.ndarray,
    token_names: tuple[str, ...],
) -> np.ndarray:
    panel = image.copy()
    _draw_grid(panel)
    for entity in np.flatnonzero(mask).tolist():
        token = int(ids[entity])
        name = token_names[token] if 0 <= token < len(token_names) else f"id={token}"
        own = features[entity, 2] >= features[entity, 3]
        color = (255, 215, 70) if own else (80, 80, 255)
        center = _source_pixel(float(features[entity, 0]), float(features[entity, 1]))
        cv2.drawMarker(panel, center, color, cv2.MARKER_CROSS, 12, 2)
        motion_confidence = float(min(feature_confidence[entity, 27:29]))
        if motion_confidence > 0.0:
            # Canonical orientation is a 180-degree rotation of source video.
            dx = -float(features[entity, 27])
            dy = -float(features[entity, 28])
            end = (round(center[0] + 22 * dx), round(center[1] + 22 * dy))
            cv2.arrowedLine(panel, center, end, color, 1, cv2.LINE_AA, tipLength=0.35)
        hp_confidence = float(feature_confidence[entity, 9])
        hp_label = (
            f"hp~{float(features[entity, 9]):.2f}/{hp_confidence:.2f}"
            if hp_confidence > 0.0
            else "hp=?"
        )
        label = f"{name} id={float(id_confidence[entity]):.2f} {hp_label}"
        cv2.putText(
            panel,
            label,
            (max(1, center[0] - 48), max(12, center[1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.30,
            color,
            1,
            cv2.LINE_AA,
        )
    cv2.rectangle(panel, (0, 0), (IMAGE_WIDTH, 54), (0, 0, 0), -1)
    cv2.putText(
        panel,
        f"frame={frame} causal actor tensors: crosses=centers, never hitboxes",
        (5, 19),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.43,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        panel,
        "arrows=tracked motion; hp=value/confidence; ?=not observed",
        (5, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )
    return panel


def _contact_sheet(images: list[np.ndarray], columns: int) -> np.ndarray:
    if not images:
        raise ValueError("cannot render an empty contact sheet")
    columns = max(1, columns)
    rows = (len(images) + columns - 1) // columns
    cell_width = IMAGE_WIDTH // 2
    cell_height = IMAGE_HEIGHT // 2
    sheet = np.zeros((rows * cell_height, columns * cell_width, 3), dtype=np.uint8)
    for index, image in enumerate(images):
        resized = cv2.resize(image, (cell_width, cell_height), interpolation=cv2.INTER_AREA)
        row, column = divmod(index, columns)
        sheet[
            row * cell_height : (row + 1) * cell_height,
            column * cell_width : (column + 1) * cell_width,
        ] = resized
    return sheet


def main() -> None:
    args = parse_args()
    if args.samples <= 0 or args.columns <= 0:
        raise ValueError("samples and columns must be positive")
    corpus = np.load(Path(args.corpus), allow_pickle=False)
    public = np.load(Path(args.public_sidecar), allow_pickle=False)
    frames = public["source_frames"].astype(np.int64, copy=False)
    if not np.array_equal(frames, corpus["source_frames"]):
        raise ValueError("corpus and public sidecar frames are not aligned")
    indices = _selected_indices(int(frames.size), args.samples)
    selected_frames = {int(frames[index]) for index in indices.tolist()}
    decoded = _decode_selected(Path(args.input_parquet), selected_frames)
    names = _token_names(corpus)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[np.ndarray] = []
    files: list[str] = []
    for audit_index, row in enumerate(indices.tolist()):
        frame = int(frames[row])
        panel = _render_row(
            decoded[frame],
            frame=frame,
            ids=public["entity_ids"][row],
            features=public["entity_features"][row],
            mask=public["entity_mask"][row],
            id_confidence=public["entity_id_confidence"][row],
            feature_confidence=public["entity_feature_confidence"][row],
            token_names=names,
        )
        path = output_dir / f"{audit_index:03d}_frame_{frame:05d}.jpg"
        if not cv2.imwrite(str(path), panel):
            raise RuntimeError(f"could not write {path}")
        rendered.append(panel)
        files.append(str(path.resolve()))
    contact_sheet = output_dir / "contact_sheet.jpg"
    if not cv2.imwrite(str(contact_sheet), _contact_sheet(rendered, args.columns)):
        raise RuntimeError(f"could not write {contact_sheet}")
    manifest: dict[str, Any] = {
        "schema": "causal-vision-actor-tensor-audit-v1",
        "input_parquet": str(Path(args.input_parquet).resolve()),
        "corpus": str(Path(args.corpus).resolve()),
        "public_sidecar": str(Path(args.public_sidecar).resolve()),
        "samples": len(files),
        "frames": [int(frames[index]) for index in indices.tolist()],
        "files": files,
        "contact_sheet": str(contact_sheet.resolve()),
        "geometry_contract": "crosses are observed sprite centers, not combat hitboxes",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
