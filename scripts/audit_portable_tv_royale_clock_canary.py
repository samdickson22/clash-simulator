from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any

import cv2
import numpy as np

CLOCK_REGION = (0.805, 0.165, 0.195, 0.075)
CANONICAL_CLOCK_SIZE = (230, 192)
CANONICAL_FRAME_SIZE = (1182, 2560)
TEACHER_CONFIDENCE_MINIMUM = 0.8
SUPPORTED_NATIVE_LAYOUTS = {(1182, 2560), (886, 1920), (888, 1920)}
RETAINED_LAYOUT = (296, 640)
NORMALIZATION_SCHEMA = (
    "clasher.youtube.clock_geometry.retained_format18_296x640_to_230x192.v1"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            for row in rows:
                output.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
                output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _load_provider(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("frozen_portable_clock", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import portable clock provider: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clock_crop(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    x, y, box_width, box_height = CLOCK_REGION
    x1, y1 = round(x * width), round(y * height)
    x2, y2 = round((x + box_width) * width), round((y + box_height) * height)
    crop = frame[y1:y2, x1:x2]
    return cv2.resize(crop, CANONICAL_CLOCK_SIZE, interpolation=cv2.INTER_CUBIC)


def _canonical_frame(clock_crop: np.ndarray) -> np.ndarray:
    width, height = CANONICAL_FRAME_SIZE
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    x, y, box_width, box_height = CLOCK_REGION
    x1, y1 = round(x * width), round(y * height)
    x2, y2 = round((x + box_width) * width), round((y + box_height) * height)
    if clock_crop.shape[:2] != (y2 - y1, x2 - x1):
        raise ValueError("normalized clock crop differs from canonical geometry")
    frame[y1:y2, x1:x2] = clock_crop
    return frame


def _parse_teacher(payload: dict[str, Any]) -> tuple[int | None, float, list[str]]:
    raw: list[str] = []
    for candidate in payload.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        text = str(candidate.get("text", ""))
        raw.append(text)
        confidence = float(candidate.get("confidence", 0.0))
        match = re.search(r"\b(\d):([0-5]\d)\b", text)
        if match is not None and confidence >= TEACHER_CONFIDENCE_MINIMUM:
            return int(match.group(1)) * 60 + int(match.group(2)), confidence, raw
    return None, 0.0, raw


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    teacher = [row for row in rows if row["teacher_seconds"] is not None]
    portable = [row for row in rows if row["portable_seconds"] is not None]
    joint = [
        row
        for row in rows
        if row["teacher_seconds"] is not None and row["portable_seconds"] is not None
    ]
    correct = [row for row in joint if row["exact_match"]]
    return {
        "frames": len(rows),
        "teacher_confident": len(teacher),
        "teacher_coverage": len(teacher) / len(rows) if rows else 0.0,
        "portable_accepted": len(portable),
        "portable_raw_coverage": len(portable) / len(rows) if rows else 0.0,
        "joint_accepted": len(joint),
        "teacher_conditioned_portable_coverage": (
            len(joint) / len(teacher) if teacher else 0.0
        ),
        "correct": len(correct),
        "conditional_exact_accuracy": len(correct) / len(joint) if joint else 0.0,
        "mismatches": [row["frame_key"] for row in joint if not row["exact_match"]],
    }


def _write_mismatch_visual(
    *, row: dict[str, Any], root: Path, output: Path
) -> None:
    frame = cv2.imread(str(root / row["path"]), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError(f"could not decode mismatch frame {row['path']}")
    crop = _clock_crop(frame)
    enlarged = cv2.resize(frame, (592, 1280), interpolation=cv2.INTER_NEAREST)
    crop_large = cv2.resize(crop, (460, 384), interpolation=cv2.INTER_NEAREST)
    canvas = np.full((1280, 1052, 3), 245, dtype=np.uint8)
    canvas[:, :592] = enlarged
    canvas[:384, 592:] = crop_large
    lines = [
        row["frame_key"],
        f"Vision teacher: {row['teacher_seconds']} s",
        f"Portable: {row['portable_seconds']} s",
        f"Portable confidence: {row['portable_confidence']:.6f}",
        f"Native source layout: {row['native_layout']}",
        f"Retained frame layout: {row['retained_layout']}",
    ]
    for index, line in enumerate(lines):
        cv2.putText(
            canvas,
            line,
            (610, 450 + index * 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (20, 20, 20),
            2,
            cv2.LINE_AA,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), canvas):
        raise RuntimeError(f"could not write mismatch visual {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canary-root", type=Path, required=True)
    parser.add_argument("--metadata-manifest", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--vision-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.canary_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    canary_manifest_path = root / "manifest.json"
    canary = json.loads(canary_manifest_path.read_text(encoding="utf-8"))
    metadata = json.loads(args.metadata_manifest.read_text(encoding="utf-8"))
    native_by_id = {
        str(row["id"]): (int(row["width"]), int(row["height"]))
        for row in metadata["videos"]
    }
    provider = _load_provider(args.provider.resolve())

    frame_specs: list[dict[str, Any]] = []
    for video in canary["videos"]:
        video_id = str(video["id"])
        native_layout = native_by_id[video_id]
        if native_layout not in SUPPORTED_NATIVE_LAYOUTS:
            raise ValueError(f"undeclared native layout {native_layout} for {video_id}")
        for section in video["sections"]:
            for frame_spec in section["frames"]:
                frame_specs.append(
                    {
                        "video_id": video_id,
                        "section": str(section["label"]),
                        "path": str(frame_spec["path"]),
                        "expected_sha256": str(frame_spec["sha256"]),
                        "native_layout": native_layout,
                    }
                )
    if len(frame_specs) != 120 or len({item["path"] for item in frame_specs}) != 120:
        raise ValueError("replay-disjoint canary must contain exactly 120 unique frames")

    with tempfile.TemporaryDirectory(prefix="clasher-clock-disjoint-") as temporary:
        temporary_root = Path(temporary)
        crop_paths: list[Path] = []
        prepared: list[dict[str, Any]] = []
        for index, item in enumerate(frame_specs):
            path = root / item["path"]
            if _sha256(path) != item["expected_sha256"]:
                raise ValueError(f"retained frame hash mismatch: {path}")
            frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError(f"could not decode retained frame {path}")
            retained_layout = (frame.shape[1], frame.shape[0])
            if retained_layout != RETAINED_LAYOUT:
                raise ValueError(
                    f"undeclared retained layout {retained_layout} for {path}"
                )
            crop = _clock_crop(frame)
            crop_path = temporary_root / f"clock_{index:03d}.png"
            teacher_crop = cv2.resize(crop, (460, 384), interpolation=cv2.INTER_CUBIC)
            if not cv2.imwrite(str(crop_path), teacher_crop):
                raise RuntimeError(f"could not write teacher crop {crop_path}")
            portable_result = provider.recognize_current_frame(_canonical_frame(crop))
            prepared.append(
                {
                    **item,
                    "frame_key": f"{item['video_id']}/{item['section']}/{path.name}",
                    "frame_sha256": item["expected_sha256"],
                    "crop_sha256": _sha256(crop_path),
                    "retained_layout": retained_layout,
                    "portable_seconds": (
                        int(portable_result[0]) if portable_result is not None else None
                    ),
                    "portable_confidence": (
                        float(portable_result[1]) if portable_result is not None else 0.0
                    ),
                    "normalization_schema": NORMALIZATION_SCHEMA,
                }
            )
            crop_paths.append(crop_path)
        vision_binary = temporary_root / "recognize_public_text"
        compile_result = subprocess.run(
            ["swiftc", str(args.vision_source.resolve()), "-o", str(vision_binary)],
            capture_output=True,
            text=True,
            check=False,
        )
        if compile_result.returncode != 0:
            raise RuntimeError(f"Vision teacher compile failed: {compile_result.stderr}")
        vision_result = subprocess.run(
            [str(vision_binary), *map(str, crop_paths)],
            capture_output=True,
            text=True,
            check=False,
        )
        if vision_result.returncode != 0:
            raise RuntimeError(f"Vision teacher failed: {vision_result.stderr}")
        teacher_payloads = [
            json.loads(line) for line in vision_result.stdout.splitlines() if line.strip()
        ]
        if len(teacher_payloads) != len(prepared):
            raise ValueError("Vision teacher row count differs from prepared frames")

    rows: list[dict[str, Any]] = []
    for item, teacher_payload in zip(prepared, teacher_payloads, strict=True):
        teacher_seconds, teacher_confidence, raw_text = _parse_teacher(teacher_payload)
        portable_seconds = item["portable_seconds"]
        rows.append(
            {
                **item,
                "native_layout": list(item["native_layout"]),
                "retained_layout": list(item["retained_layout"]),
                "teacher_seconds": teacher_seconds,
                "teacher_confidence": teacher_confidence,
                "teacher_raw_text": raw_text,
                "teacher_current_frame_only": True,
                "exact_match": (
                    teacher_seconds is not None
                    and portable_seconds is not None
                    and teacher_seconds == portable_seconds
                ),
            }
        )
    rows_path = output_dir / "frame_audit.jsonl"
    _atomic_jsonl(rows_path, rows)

    by_video: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_layout: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_video[row["video_id"]].append(row)
        by_layout[f"{row['native_layout'][0]}x{row['native_layout'][1]}"] .append(row)
    mismatch_visuals: list[dict[str, str]] = []
    for row in rows:
        if row["teacher_seconds"] is None or row["portable_seconds"] is None:
            continue
        if row["exact_match"]:
            continue
        output = output_dir / "mismatches" / f"{row['video_id']}_{row['section']}_{Path(row['path']).stem}.png"
        _write_mismatch_visual(row=row, root=root, output=output)
        mismatch_visuals.append(
            {"path": str(output), "sha256": _sha256(output), "frame_key": row["frame_key"]}
        )

    overall = _metrics(rows)
    gates = {
        "exactly_120_hashed_frames": len(rows) == 120,
        "teacher_coverage_at_least_0_80": overall["teacher_coverage"] >= 0.80,
        "teacher_conditioned_portable_coverage_at_least_0_80": (
            overall["teacher_conditioned_portable_coverage"] >= 0.80
        ),
        "conditional_exact_accuracy_at_least_0_99": (
            overall["conditional_exact_accuracy"] >= 0.99
        ),
        "all_native_layouts_represented": set(by_layout) == {
            "886x1920",
            "888x1920",
            "1182x2560",
        },
    }
    report = {
        "schema": "clasher.youtube.portable_clock_replay_disjoint_audit.v1",
        "decision": (
            "pass_replay_disjoint_gate" if all(gates.values()) else "fail_replay_disjoint_gate"
        ),
        "provider": {
            "path": str(args.provider.resolve()),
            "sha256": _sha256(args.provider.resolve()),
            "templates_retrained": False,
        },
        "authority": {
            "canary_manifest": {
                "path": str(canary_manifest_path),
                "sha256": _sha256(canary_manifest_path),
            },
            "metadata_manifest": {
                "path": str(args.metadata_manifest.resolve()),
                "sha256": _sha256(args.metadata_manifest.resolve()),
            },
            "vision_teacher_source": {
                "path": str(args.vision_source.resolve()),
                "sha256": _sha256(args.vision_source.resolve()),
                "confidence_minimum": TEACHER_CONFIDENCE_MINIMUM,
            },
        },
        "geometry": {
            "normalization_schema": NORMALIZATION_SCHEMA,
            "retained_frame_layout": list(RETAINED_LAYOUT),
            "canonical_clock_layout": list(CANONICAL_CLOCK_SIZE),
            "native_layouts_are_metadata_provenance_not_retained_pixel_geometry": True,
            "native_886_888_provider_support": "not_enabled; remains fail-closed",
        },
        "overall": overall,
        "per_video": {key: _metrics(value) for key, value in sorted(by_video.items())},
        "per_native_layout": {
            key: _metrics(value) for key, value in sorted(by_layout.items())
        },
        "rows": {
            "path": str(rows_path),
            "sha256": _sha256(rows_path),
            "count": len(rows),
        },
        "mismatch_visuals": mismatch_visuals,
        "gates": gates,
        "failed_gates": [name for name, passed in gates.items() if not passed],
    }
    report_path = output_dir / "report.json"
    _atomic_json(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
