from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import gzip
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

import cv2
import numpy as np

from scripts.build_tv_royale_hud_cluster_gallery import _card_art_region
from scripts.extract_tv_royale_youtube_fullmatch import (
    HUD_ROIS,
    _atomic_json,
    _crop_relative,
    _sha256,
)

SCHEMA = "clasher.youtube.eight_card_deck_sheet.v1"
NEXT_CHANGE_SIMILARITY = 0.90
NEXT_STABILITY_SIMILARITY = 0.97
NEXT_STABILITY_FRAMES = 3


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


def _art_vector(crop: np.ndarray) -> np.ndarray:
    art = cv2.resize(
        _card_art_region(crop), (32, 32), interpolation=cv2.INTER_AREA
    )
    grayscale = cv2.cvtColor(art, cv2.COLOR_BGR2GRAY).astype(np.float32).reshape(-1)
    grayscale -= float(grayscale.mean())
    return np.asarray(grayscale / max(float(np.linalg.norm(grayscale)), 1e-8))


def _heads_visible(record: dict[str, Any], player_id: int) -> bool:
    hud = record["offline_privileged_hud"][str(player_id)]
    heads = [*hud["hand"], hud["next_card"]]
    return bool(
        hud["elixir"].get("valid")
        and all(head.get("candidate") not in {None, "empty"} for head in heads)
    )


def _color_score(crop: np.ndarray) -> float:
    hsv = cv2.cvtColor(_card_art_region(crop), cv2.COLOR_BGR2HSV)
    return float(np.mean(hsv[:, :, 1]))


@dataclass
class PlayerDeckState:
    player_id: int
    initial_frame: int | None = None
    hand_crops: list[np.ndarray] = field(default_factory=list)
    next_crops: list[np.ndarray] = field(default_factory=list)
    next_frames: list[int] = field(default_factory=list)
    current_next: np.ndarray | None = None
    candidate_next: np.ndarray | None = None
    candidate_crop: np.ndarray | None = None
    candidate_frame: int | None = None
    candidate_streak: int = 0
    initial_candidate_crops: list[np.ndarray] = field(default_factory=list)
    initial_candidate_vectors: list[np.ndarray] = field(default_factory=list)
    initial_candidate_frame: int | None = None
    initial_candidate_streak: int = 0
    hand_vectors: list[np.ndarray] = field(default_factory=list)
    hand_color_scores: list[float] = field(default_factory=list)
    next_color_scores: list[float] = field(default_factory=list)

    def observe_initial(self, frame_index: int, crops: list[np.ndarray]) -> None:
        if any(float(np.std(_card_art_region(crop))) < 12.0 for crop in crops):
            self.initial_candidate_crops = []
            self.initial_candidate_vectors = []
            self.initial_candidate_frame = None
            self.initial_candidate_streak = 0
            return
        vectors = [_art_vector(crop) for crop in crops]
        stable = bool(
            self.initial_candidate_vectors
            and all(
                float(current @ previous) >= NEXT_STABILITY_SIMILARITY
                for current, previous in zip(
                    vectors, self.initial_candidate_vectors, strict=True
                )
            )
        )
        if stable:
            self.initial_candidate_streak += 1
        else:
            self.initial_candidate_crops = [crop.copy() for crop in crops]
            self.initial_candidate_vectors = vectors
            self.initial_candidate_frame = frame_index
            self.initial_candidate_streak = 1
        if self.initial_candidate_streak >= NEXT_STABILITY_FRAMES:
            assert self.initial_candidate_frame is not None
            self.initialize(
                self.initial_candidate_frame, self.initial_candidate_crops
            )

    def initialize(self, frame_index: int, crops: list[np.ndarray]) -> None:
        self.initial_frame = frame_index
        self.hand_crops = [crop.copy() for crop in crops[:4]]
        self.next_crops = [crops[4].copy()]
        self.next_frames = [frame_index]
        self.hand_vectors = [_art_vector(crop) for crop in crops[:4]]
        self.hand_color_scores = [_color_score(crop) for crop in crops[:4]]
        self.next_color_scores = [_color_score(crops[4])]
        self.current_next = _art_vector(crops[4])

    def retain_best_visible_crops(self, crops: list[np.ndarray]) -> None:
        for index in range(4):
            vector = _art_vector(crops[index])
            score = _color_score(crops[index])
            if (
                float(vector @ self.hand_vectors[index]) >= NEXT_CHANGE_SIMILARITY
                and score > self.hand_color_scores[index]
            ):
                self.hand_crops[index] = crops[index].copy()
                self.hand_color_scores[index] = score
        if self.current_next is None:
            return
        next_vector = _art_vector(crops[4])
        next_score = _color_score(crops[4])
        if (
            float(next_vector @ self.current_next) >= NEXT_CHANGE_SIMILARITY
            and next_score > self.next_color_scores[-1]
        ):
            self.next_crops[-1] = crops[4].copy()
            self.next_color_scores[-1] = next_score

    def observe_next(self, frame_index: int, crop: np.ndarray) -> None:
        if self.current_next is None or len(self.next_crops) >= 4:
            return
        vector = _art_vector(crop)
        if float(vector @ self.current_next) >= NEXT_CHANGE_SIMILARITY:
            self.candidate_next = None
            self.candidate_crop = None
            self.candidate_frame = None
            self.candidate_streak = 0
            return
        if (
            self.candidate_next is not None
            and float(vector @ self.candidate_next) >= NEXT_STABILITY_SIMILARITY
        ):
            self.candidate_streak += 1
        else:
            self.candidate_next = vector
            self.candidate_crop = crop.copy()
            self.candidate_frame = frame_index
            self.candidate_streak = 1
        if self.candidate_streak < NEXT_STABILITY_FRAMES:
            return
        assert self.candidate_next is not None
        assert self.candidate_crop is not None
        assert self.candidate_frame is not None
        self.current_next = self.candidate_next
        self.next_crops.append(self.candidate_crop)
        self.next_frames.append(self.candidate_frame)
        self.next_color_scores.append(_color_score(self.candidate_crop))
        self.candidate_next = None
        self.candidate_crop = None
        self.candidate_frame = None
        self.candidate_streak = 0


def _write_sheet(
    states: dict[int, PlayerDeckState], output: Path, *, sample_hz: int
) -> None:
    cell_width = 180
    cell_height = 235
    label_height = 34
    sheet = np.full((cell_height * 2, cell_width * 8, 3), 18, dtype=np.uint8)
    for player_id in (0, 1):
        state = states[player_id]
        crops = [*state.hand_crops, *state.next_crops]
        labels = [f"P{player_id} hand {index}" for index in range(4)] + [
            f"P{player_id} queue {index} t={frame / sample_hz:.1f}s"
            for index, frame in enumerate(state.next_frames)
        ]
        for index, (crop, label) in enumerate(zip(crops, labels, strict=True)):
            resized = cv2.resize(
                crop, (cell_width, cell_height - label_height), interpolation=cv2.INTER_AREA
            )
            x = index * cell_width
            y = player_id * cell_height
            sheet[y + label_height : y + cell_height, x : x + cell_width] = resized
            cv2.putText(
                sheet,
                label,
                (x + 5, y + 23),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
    if not cv2.imwrite(str(output), sheet, [cv2.IMWRITE_JPEG_QUALITY, 96]):
        raise ValueError(f"could not write deck sheet {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--neutral", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    sample_hz = int(str(source["decode"]["output_time_base"]).split("/", 1)[1])
    with gzip.open(args.neutral, "rt", encoding="utf-8") as input_file:
        neutral = [json.loads(line) for line in input_file if line.strip()]
    if len(neutral) != int(source["decode"]["sample_count"]):
        raise ValueError("neutral rows do not match source samples")

    process = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(args.video.resolve()),
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
    frame_size = 591 * 1280 * 3
    states = {player_id: PlayerDeckState(player_id) for player_id in (0, 1)}
    frame_index = 0
    while True:
        raw = _read_exact(process.stdout, frame_size)
        if not raw:
            break
        if len(raw) != frame_size:
            raise ValueError(f"short frame {frame_index}")
        frame = np.frombuffer(raw, dtype=np.uint8).reshape(1280, 591, 3)
        record = neutral[min(frame_index, len(neutral) - 1)]
        for player_id in (0, 1):
            state = states[player_id]
            layout = HUD_ROIS[player_id]
            boxes = [*layout["hand"], layout["next"]]
            crops = [np.ascontiguousarray(_crop_relative(frame, box)) for box in boxes]
            if state.initial_frame is None:
                if frame_index >= sample_hz * 2 and _heads_visible(record, player_id):
                    state.observe_initial(frame_index, crops)
            else:
                state.retain_best_visible_crops(crops)
                state.observe_next(frame_index, crops[4])
        frame_index += 1
    process.stdout.close()
    stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
    if process.wait() != 0:
        raise RuntimeError(f"ffmpeg deck-sheet decode failed: {stderr[-1000:]}")
    for state in states.values():
        if state.initial_frame is None or len(state.hand_crops) != 4:
            raise ValueError(f"player {state.player_id} has no complete initial HUD")
        if len(state.next_crops) != 4:
            raise ValueError(
                f"player {state.player_id} exposed only {len(state.next_crops)} queue cards"
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    card_root = args.output_dir / "cards"
    card_root.mkdir(parents=True, exist_ok=True)
    card_artifacts: dict[str, list[dict[str, Any]]] = {}
    for player_id, state in states.items():
        player_rows: list[dict[str, Any]] = []
        for card_index, crop in enumerate([*state.hand_crops, *state.next_crops]):
            path = card_root / f"p{player_id}_card_{card_index}.png"
            if not cv2.imwrite(str(path), crop):
                raise ValueError(f"could not write deck card crop {path}")
            player_rows.append(
                {
                    "card_index": card_index,
                    "source": "initial_hand" if card_index < 4 else "queue_reveal",
                    "path": str(path),
                    "sha256": _sha256(path),
                    "color_score": (
                        state.hand_color_scores[card_index]
                        if card_index < 4
                        else state.next_color_scores[card_index - 4]
                    ),
                }
            )
        card_artifacts[str(player_id)] = player_rows
    sheet_path = args.output_dir / "eight_card_deck_sheet.jpg"
    _write_sheet(states, sheet_path, sample_hz=sample_hz)
    manifest = {
        "schema": SCHEMA,
        "video_id": source["source"]["video_id"],
        "video_sha256": _sha256(args.video),
        "source_manifest_sha256": _sha256(args.source_manifest),
        "neutral_sha256": _sha256(args.neutral),
        "sample_hz": sample_hz,
        "contract": {
            "initial_cards": "first stable four-hand plus visible Next current-frame crops",
            "remaining_cards": "first three stable current-frame Next-art changes",
            "identity_labels": "none; review required",
            "external_history_or_lookup": False,
        },
        "players": {
            str(player_id): {
                "initial_frame": state.initial_frame,
                "initial_timestamp_ms": round(state.initial_frame * 1000 / sample_hz),
                "next_frames": state.next_frames,
                "next_timestamps_ms": [
                    round(frame * 1000 / sample_hz) for frame in state.next_frames
                ],
                "cards_exposed": 8,
                "card_artifacts": card_artifacts[str(player_id)],
            }
            for player_id, state in states.items()
            if state.initial_frame is not None
        },
        "artifact": {"path": str(sheet_path), "sha256": _sha256(sheet_path)},
        "status": "identity_review_required",
    }
    manifest_path = args.output_dir / "manifest.json"
    _atomic_json(manifest_path, manifest)
    print(json.dumps({"manifest": str(manifest_path), "sheet": str(sheet_path)}, indent=2))


if __name__ == "__main__":
    main()
