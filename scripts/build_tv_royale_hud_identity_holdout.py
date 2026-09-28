from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from scripts.extract_tv_royale_youtube_fullmatch import HUD_ROIS, _crop_relative

SCHEMA = "clasher.youtube.hud_identity_holdout.v1"
OFFSETS_MS = (-1_100, -800, -500)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_unique_slot_events(
    gold: dict[str, Any], action_labels: dict[str, Any]
) -> list[dict[str, Any]]:
    source_rows = action_labels.get("labels", action_labels.get("rows"))
    if not isinstance(source_rows, list):
        raise TypeError("action labels require labels or rows")
    predictions = {row["label_id"]: row for row in source_rows}
    selected: list[dict[str, Any]] = []
    for row in gold["labels"]:
        if not row.get("play_valid") or not row.get("identity_valid"):
            continue
        prediction = predictions.get(row["label_id"])
        if prediction is None:
            raise ValueError(f"missing action label {row['label_id']}")
        candidates = prediction.get("identity_candidates", [])
        transition_candidate: str | None
        transition_agrees: bool | None
        if len(candidates) == 1 and isinstance(candidates[0], dict):
            candidate = candidates[0]
            slot = int(candidate["slot"])
            transition_candidate = str(candidate["card_identity"])
            transition_agrees = candidate["card_identity"] == row["card_identity"]
            slot_evidence = "unique_identity_candidate_transition"
        elif (
            isinstance(prediction.get("selected_slot"), int)
            and prediction.get("transition_evidence")
            in {
                "unique_next_enters_changed_slot",
                "unique_changed_slot_without_next_confirmation",
            }
        ):
            slot = int(prediction["selected_slot"])
            transition_candidate = None
            transition_agrees = None
            slot_evidence = str(prediction["transition_evidence"])
        else:
            continue
        if not 0 <= slot < 4:
            raise ValueError(f"invalid transitioned slot for {row['label_id']}")
        selected.append(
            {
                "label_id": str(row["label_id"]),
                "player_id": int(row["player_id"]),
                "timestamp_ms": int(row["timestamp_ms"]),
                "card_identity": str(row["card_identity"]),
                "slot": slot,
                "transition_candidate": transition_candidate,
                "transition_agrees_with_gold": transition_agrees,
                "slot_evidence": slot_evidence,
            }
        )
    return selected


def _frame_targets(
    events: list[dict[str, Any]], *, sample_hz: int
) -> dict[int, list[dict[str, Any]]]:
    targets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        for offset_ms in OFFSETS_MS:
            timestamp_ms = event["timestamp_ms"] + offset_ms
            if timestamp_ms < 0:
                continue
            output_pts = round(timestamp_ms * sample_hz / 1_000)
            targets[output_pts].append({**event, "crop_timestamp_ms": timestamp_ms})
    return dict(targets)


def _contact_sheet(crops: list[tuple[Path, dict[str, Any]]], output: Path) -> None:
    first_by_class: dict[str, tuple[Path, dict[str, Any]]] = {}
    for item in crops:
        first_by_class.setdefault(item[1]["card_identity"], item)
    chosen = [first_by_class[key] for key in sorted(first_by_class)]
    cell_width, cell_height = 240, 260
    columns = 4
    rows = (len(chosen) + columns - 1) // columns
    canvas = np.full((rows * cell_height, columns * cell_width, 3), 24, np.uint8)
    for index, (path, record) in enumerate(chosen):
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"could not read contact crop {path}")
        scale = min(190 / image.shape[1], 190 / image.shape[0])
        resized = cv2.resize(
            image,
            (round(image.shape[1] * scale), round(image.shape[0] * scale)),
            interpolation=cv2.INTER_NEAREST,
        )
        row, column = divmod(index, columns)
        x = column * cell_width + (cell_width - resized.shape[1]) // 2
        y = row * cell_height + 8
        canvas[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
        label = record["card_identity"].split(":", 1)[-1]
        cv2.putText(
            canvas,
            label[:25],
            (column * cell_width + 8, row * cell_height + 225),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (235, 235, 235),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            f"P{record['player_id']} slot {record['slot']}",
            (column * cell_width + 8, row * cell_height + 247),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (170, 205, 245),
            1,
            cv2.LINE_AA,
        )
    if not cv2.imwrite(str(output), canvas):
        raise ValueError(f"could not write contact sheet {output}")


def build_holdout(
    *,
    video: Path,
    source_manifest: Path,
    gold_path: Path,
    action_labels_path: Path,
    output_dir: Path,
    ffmpeg: str,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"refusing existing output directory: {output_dir}")
    acquisition = json.loads(source_manifest.read_text(encoding="utf-8"))
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    actions = json.loads(action_labels_path.read_text(encoding="utf-8"))
    events = select_unique_slot_events(gold, actions)
    if not events:
        raise ValueError("no uniquely transitioned gold events")
    if any(row["transition_agrees_with_gold"] is False for row in events):
        raise ValueError("unique transition disagrees with visual identity gold")

    decode = acquisition["decode"]
    media = acquisition["source_media"]
    sample_hz = round(float(decode.get("sample_hz", decode["cadence_hz"])))
    expected_samples = int(decode["sample_count"])
    width = int(media["width"]) // 2
    height = int(media["height"]) // 2
    frame_bytes = width * height * 3
    targets = _frame_targets(events, sample_hz=sample_hz)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent)
    )
    crops_dir = temporary / "crops"
    crops_dir.mkdir()
    process = subprocess.Popen(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            f"fps={sample_hz},scale={width}:{height}:flags=lanczos",
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
    records: list[dict[str, Any]] = []
    saved: list[tuple[Path, dict[str, Any]]] = []
    try:
        for output_pts in range(expected_samples):
            data = process.stdout.read(frame_bytes)
            if len(data) != frame_bytes:
                raise ValueError(f"short frame at output PTS {output_pts}")
            specs = targets.get(output_pts)
            if not specs:
                continue
            frame = np.frombuffer(data, np.uint8).reshape(height, width, 3)
            for spec in specs:
                box = HUD_ROIS[spec["player_id"]]["hand"][spec["slot"]]
                crop = _crop_relative(frame, box)
                filename = f"{spec['label_id']}_{output_pts:06d}.png"
                path = crops_dir / filename
                if not cv2.imwrite(str(path), crop):
                    raise ValueError(f"could not write {path}")
                record = {
                    **spec,
                    "output_pts": output_pts,
                    "output_time_base": f"1/{sample_hz}",
                    "path": f"crops/{filename}",
                    "sha256": _sha256(path),
                    "height": int(crop.shape[0]),
                    "width": int(crop.shape[1]),
                    "split": "test_replay_disjoint_holdout",
                    "label_source": "manual_visual_gold_plus_unique_slot_transition",
                }
                records.append(record)
                saved.append((path, record))
        process.stdout.close()
        stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
        if process.wait() != 0:
            raise RuntimeError(f"ffmpeg failed: {stderr[-1_000:]}")
        contact = temporary / "contact_sheet.jpg"
        _contact_sheet(saved, contact)
        payload = {
            "schema": SCHEMA,
            "source": {
                "video": str(video.resolve()),
                "video_sha256": _sha256(video),
                "manifest": str(source_manifest.resolve()),
                "manifest_sha256": _sha256(source_manifest),
                "gold_sha256": _sha256(gold_path),
                "action_labels_sha256": _sha256(action_labels_path),
            },
            "contract": {
                "slot_selection": "exactly_one_pre_play_hand_slot_transition",
                "identity_source": "independent_manual_visual_action_gold",
                "identity_not_used_to_select_slot": True,
                "all_real_crops_held_out": True,
                "same_replay_crops_never_split_across_train_eval": True,
            },
            "counts": {
                "events": len(events),
                "crops": len(records),
                "classes": len({row["card_identity"] for row in records}),
                "by_class": dict(
                    sorted(Counter(row["card_identity"] for row in records).items())
                ),
            },
            "offsets_ms": list(OFFSETS_MS),
            "records": records,
            "contact_sheet": {
                "path": contact.name,
                "sha256": _sha256(contact),
            },
        }
        manifest = temporary / "manifest.json"
        manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, output_dir)
        return payload
    except BaseException:
        process.kill()
        process.wait()
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--action-labels", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    payload = build_holdout(
        video=args.video.resolve(),
        source_manifest=args.source_manifest.resolve(),
        gold_path=args.gold.resolve(),
        action_labels_path=args.action_labels.resolve(),
        output_dir=args.output_dir.resolve(),
        ffmpeg=args.ffmpeg,
    )
    print(json.dumps(payload["counts"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
