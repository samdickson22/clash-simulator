from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import IO, Any

import cv2
import numpy as np

from scripts.audit_portable_tv_royale_clock_canary import _parse_teacher
from scripts.extract_tv_royale_youtube_fullmatch import _atomic_json, _sha256
from tools.recognize_public_clock import _clock_crop, recognize_current_frame

SCHEMA = "clasher.youtube.portable_clock_native_video_verification.v1"


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


def verify(
    *,
    video: Path,
    source_manifest: Path,
    vision_source: Path,
    sample_hz: int,
) -> dict[str, Any]:
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    width = int(manifest["source_media"]["width"])
    height = int(manifest["source_media"]["height"])
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="clasher-clock-native-") as temporary:
        root = Path(temporary)
        tool = root / "recognize_public_text"
        subprocess.run(
            ["swiftc", str(vision_source), "-o", str(tool)],
            check=True,
            capture_output=True,
            text=True,
        )
        decoder = subprocess.Popen(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video),
                "-vf",
                f"fps={sample_hz}",
                "-pix_fmt",
                "bgr24",
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert decoder.stdout is not None
        frame_bytes = width * height * 3
        portable: dict[int, tuple[int, float] | None] = {}
        paths: list[Path] = []
        frame_index = 0
        while True:
            raw = _read_exact(decoder.stdout, frame_bytes)
            if not raw:
                break
            if len(raw) != frame_bytes:
                raise ValueError(f"short frame {frame_index}")
            frame = np.frombuffer(raw, np.uint8).reshape(height, width, 3)
            portable[frame_index] = recognize_current_frame(frame)
            path = root / f"clock_{frame_index:06d}.png"
            if not cv2.imwrite(str(path), _clock_crop(frame)):
                raise ValueError(f"could not write {path}")
            paths.append(path)
            frame_index += 1
        decoder.stdout.close()
        stderr = decoder.stderr.read().decode(errors="replace") if decoder.stderr else ""
        if decoder.wait() != 0:
            raise RuntimeError(f"ffmpeg failed: {stderr[-1000:]}")
        vision = subprocess.run(
            [str(tool), *[str(path) for path in paths]],
            check=True,
            capture_output=True,
            text=True,
        )
        teacher: dict[int, tuple[int | None, float, list[str]]] = {}
        for line in vision.stdout.splitlines():
            row = json.loads(line)
            match = re.search(r"clock_(\d+)\.png$", str(row.get("path", "")))
            if match:
                teacher[int(match.group(1))] = _parse_teacher(row)
        rows = []
        for index in range(frame_index):
            teacher_seconds, teacher_confidence, teacher_text = teacher.get(
                index, (None, 0.0, [])
            )
            portable_row = portable[index]
            portable_seconds = None if portable_row is None else portable_row[0]
            portable_confidence = 0.0 if portable_row is None else portable_row[1]
            rows.append(
                {
                    "sample_index": index,
                    "teacher_seconds": teacher_seconds,
                    "teacher_confidence": teacher_confidence,
                    "teacher_text": teacher_text,
                    "portable_seconds": portable_seconds,
                    "portable_confidence": portable_confidence,
                    "joint_accepted": teacher_seconds is not None
                    and portable_seconds is not None,
                    "exact": teacher_seconds is not None
                    and portable_seconds == teacher_seconds,
                }
            )
    teacher_rows = [row for row in rows if row["teacher_seconds"] is not None]
    joint = [row for row in teacher_rows if row["portable_seconds"] is not None]
    correct = [row for row in joint if row["exact"]]
    return {
        "schema": SCHEMA,
        "source": {
            "video_sha256": _sha256(video),
            "manifest_sha256": _sha256(source_manifest),
            "width": width,
            "height": height,
            "sample_hz": sample_hz,
        },
        "counts": {
            "frames": len(rows),
            "teacher_confident": len(teacher_rows),
            "portable_accepted": sum(row["portable_seconds"] is not None for row in rows),
            "joint_accepted": len(joint),
            "correct": len(correct),
            "false_accepts": len(joint) - len(correct),
        },
        "metrics": {
            "teacher_conditioned_coverage": (
                len(joint) / len(teacher_rows) if teacher_rows else None
            ),
            "conditional_exact_accuracy": len(correct) / len(joint) if joint else None,
        },
        "wall_seconds": time.perf_counter() - started,
        "mismatches": [row for row in joint if not row["exact"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument(
        "--vision-source", type=Path, default=Path("tools/recognize_public_text.swift")
    )
    parser.add_argument("--sample-hz", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = verify(
        video=args.video,
        source_manifest=args.source_manifest,
        vision_source=args.vision_source,
        sample_hz=args.sample_hz,
    )
    _atomic_json(args.output, payload)
    print(json.dumps({"output": str(args.output), **payload["counts"]}, indent=2))


if __name__ == "__main__":
    main()
