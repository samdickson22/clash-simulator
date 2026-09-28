from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import copy
import gzip
import json
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from scripts.extract_tv_royale_youtube_fullmatch import (
    HUD_ROIS,
    _atomic_gzip_jsonl,
    _atomic_json,
    _crop_relative,
    _sha256,
)

SCHEMA = "clasher.youtube.visible_cost_gate.v1"


def _rows(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _cost_authority(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text())
    output = {}
    for row in payload["entries"]:
        if row["namespace"] != "card_action":
            continue
        cost = row.get("mana_cost")
        if isinstance(cost, int) and not isinstance(cost, bool):
            output[str(row["stable_key"])] = cost
    return output


def _occurrences(
    rows: list[dict[str, Any]], maximum_per_family: int
) -> list[dict[str, Any]]:
    by_family: dict[tuple[int, str], list[tuple[int, int, float]]] = defaultdict(list)
    for index, row in enumerate(rows):
        for player_id in (0, 1):
            for slot, head in enumerate(
                row["offline_privileged_hud"][str(player_id)]["hand"]
            ):
                value = head.get("value")
                if head.get("valid") and isinstance(value, str) and value != "empty":
                    by_family[(player_id, value)].append(
                        (index, slot, float(head.get("score", 0.0)))
                    )
    output = []
    for (player_id, family), values in sorted(by_family.items()):
        if len(values) < 20:
            continue
        selected = np.linspace(
            0, len(values) - 1, min(maximum_per_family, len(values)), dtype=np.int64
        )
        for order, selected_index in enumerate(selected.tolist()):
            frame, slot, score = values[selected_index]
            output.append(
                {
                    "player_id": player_id,
                    "family": family,
                    "frame": frame,
                    "slot": slot,
                    "score": score,
                    "split": "calibration"
                    if order < round(len(selected) * 0.7)
                    else "same_match_diagnostic",
                }
            )
    return output


def _digit_glyph(image: np.ndarray) -> np.ndarray | None:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    upper = hsv[: max(1, round(hsv.shape[0] * 0.72))]
    magenta = (
        (upper[:, :, 0] > 130)
        & (upper[:, :, 0] < 180)
        & (upper[:, :, 1] > 80)
        & (upper[:, :, 2] > 50)
    )
    ys, xs = np.where(magenta)
    if not len(xs):
        return None
    badge = image[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    badge_hsv = cv2.cvtColor(badge, cv2.COLOR_BGR2HSV)
    white = ((badge_hsv[:, :, 1] < 100) & (badge_hsv[:, :, 2] > 140)).astype(
        np.uint8
    ) * 255
    count, _, stats, _ = cv2.connectedComponentsWithStats(white)
    candidates = []
    for component in range(1, count):
        x, y, width, height, area = stats[component]
        aspect = width / max(1, height)
        if area > 10 and 0.1 < aspect < 1.5 and x > 1 and y > 1:
            candidates.append((area, component))
    if not candidates:
        return None
    _, component = max(candidates)
    x, y, width, height, _ = stats[component]
    glyph = white[y : y + height, x : x + width]
    canvas: np.ndarray = np.full((128, 128), 255, dtype=np.uint8)
    scale = min(90 / width, 90 / height)
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    resized = 255 - cv2.resize(
        glyph,
        (resized_width, resized_height),
        interpolation=cv2.INTER_NEAREST,
    )
    offset_x = (128 - resized_width) // 2
    offset_y = (128 - resized_height) // 2
    canvas[
        offset_y : offset_y + resized_height,
        offset_x : offset_x + resized_width,
    ] = resized
    return canvas


def _cost_box(player_id: int, slot: int) -> tuple[float, float, float, float]:
    x = float(HUD_ROIS[player_id]["hand"][slot][0])
    return (
        (x + 0.025, 0.905, 0.085, 0.070)
        if player_id == 0
        else (x + 0.025, 0.125, 0.085, 0.070)
    )


def _extract_glyphs(
    *,
    video: Path,
    occurrences: list[dict[str, Any]],
    output: Path,
) -> None:
    by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in occurrences:
        by_frame[int(item["frame"])].append(item)
    command = [
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
    ]
    decoder = subprocess.Popen(command, stdout=subprocess.PIPE)
    assert decoder.stdout is not None
    frame_bytes = 591 * 1280 * 3
    glyph_root = output / "glyphs"
    glyph_root.mkdir(parents=True, exist_ok=True)
    for frame in range(3204):
        raw = decoder.stdout.read(frame_bytes)
        if len(raw) != frame_bytes:
            raise ValueError(f"short decode at frame {frame}")
        if frame not in by_frame:
            continue
        image = np.frombuffer(raw, dtype=np.uint8).reshape(1280, 591, 3)
        for item in by_frame[frame]:
            crop = _crop_relative(
                image, _cost_box(int(item["player_id"]), int(item["slot"]))
            )
            crop = cv2.resize(
                crop,
                None,
                fx=3.0,
                fy=3.0,
                interpolation=cv2.INTER_CUBIC,
            )
            glyph = _digit_glyph(crop)
            if glyph is None:
                item["glyph_valid"] = False
                continue
            path = glyph_root / (
                f"p{item['player_id']}_{item['family'].split(':', 1)[-1]}_"
                f"f{frame:04d}_s{item['slot']}_{item['split']}.png"
            )
            if not cv2.imwrite(str(path), glyph):
                raise ValueError(f"could not write {path}")
            item["glyph_valid"] = True
            item["glyph_path"] = str(path)
            item["glyph_sha256"] = _sha256(path)
    decoder.stdout.close()
    if decoder.wait() != 0:
        raise ValueError("ffmpeg glyph decode failed")


def _ocr(occurrences: list[dict[str, Any]], swift_source: Path, output: Path) -> None:
    valid = [item for item in occurrences if item.get("glyph_valid")]
    if not valid:
        return
    binary = output / "recognize_public_cost"
    subprocess.run(["swiftc", str(swift_source), "-o", str(binary)], check=True)
    result = subprocess.run(
        [str(binary), *[str(item["glyph_path"]) for item in valid]],
        check=True,
        capture_output=True,
        text=True,
    )
    by_path = {str(item["glyph_path"]): item for item in valid}
    for line in result.stdout.splitlines():
        payload = json.loads(line)
        path = str(payload.get("path", "")).replace("\\/", "/")
        item = by_path.get(path)
        if item is None:
            continue
        predictions = []
        for candidate in payload.get("candidates", []):
            match = re.fullmatch(r"\s*(10|[1-9])\s*", str(candidate.get("text", "")))
            if match is not None:
                predictions.append(
                    (int(match.group(1)), float(candidate.get("confidence", 0.0)))
                )
        if predictions:
            item["visible_cost"] = predictions[0][0]
            item["ocr_confidence"] = predictions[0][1]
            item["ocr_valid"] = True
        else:
            item["ocr_valid"] = False


def _temporal_costs(action_labels: Path) -> dict[str, list[float]]:
    payload = json.loads(action_labels.read_text())
    output: dict[str, list[float]] = defaultdict(list)
    for label in payload["labels"]:
        for candidate in label["identity_candidates"]:
            output[str(candidate["card_identity"])].append(
                float(label["observed_elixir_drop"])
            )
    return output


def _family_evidence(
    occurrences: list[dict[str, Any]],
    authority: dict[str, int],
    temporal: dict[str, list[float]],
) -> tuple[dict[str, Any], set[str]]:
    evidence: dict[str, Any] = {}
    quarantine: set[str] = set()
    families = sorted({str(item["family"]) for item in occurrences})
    for family in families:
        rows = [item for item in occurrences if item["family"] == family]
        calibration = [
            int(item["visible_cost"])
            for item in rows
            if item["split"] == "calibration" and item.get("ocr_valid")
        ]
        diagnostic = [
            int(item["visible_cost"])
            for item in rows
            if item["split"] == "same_match_diagnostic" and item.get("ocr_valid")
        ]
        official = authority.get(family)
        mode = Counter(calibration).most_common(1)[0][0] if calibration else None
        mode_support = calibration.count(mode) if mode is not None else 0
        direct_mismatch = bool(
            official is not None
            and mode is not None
            and mode != official
            and mode_support >= 3
            and mode_support / len(calibration) >= 0.8
        )
        temporal_values = temporal.get(family, [])
        temporal_consistent_with_direct = bool(
            mode is not None
            and temporal_values
            and min(abs(value - mode) for value in temporal_values) <= 1.0
        )
        if direct_mismatch and temporal_consistent_with_direct:
            quarantine.add(family)
        diagnostic_matches_mode = (
            sum(value == mode for value in diagnostic) if mode is not None else 0
        )
        evidence[family] = {
            "official_cost": official,
            "calibration_ocr_valid": len(calibration),
            "calibration_cost_counts": dict(Counter(calibration)),
            "calibration_mode": mode,
            "calibration_mode_support": mode_support,
            "same_match_diagnostic_ocr_valid": len(diagnostic),
            "same_match_diagnostic_cost_counts": dict(Counter(diagnostic)),
            "same_match_diagnostic_matches_calibration_mode": diagnostic_matches_mode,
            "same_match_diagnostic_mode_precision": (
                diagnostic_matches_mode / len(diagnostic)
                if diagnostic and mode is not None
                else None
            ),
            "temporal_drop_observations": temporal_values,
            "direct_mismatch": direct_mismatch,
            "temporal_consistent_with_direct": temporal_consistent_with_direct,
            "quarantined": family in quarantine,
        }
    return evidence, quarantine


def _apply_gate(
    rows: list[dict[str, Any]], evidence: dict[str, Any], quarantine: set[str]
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for player_id in (0, 1):
            hud = row["offline_privileged_hud"][str(player_id)]
            for head in [*hud["hand"], hud["next_card"]]:
                value = head.get("value")
                candidate = value if isinstance(value, str) else head.get("candidate")
                if not isinstance(candidate, str) or candidate not in evidence:
                    continue
                if value in quarantine and head.get("valid"):
                    head["value"] = None
                    head["valid"] = False
                    head["reason"] = "visible_cost_family_mismatch"
                    counts[f"p{player_id}_rejected"] += 1
            hud["all_hand_valid"] = all(item["valid"] for item in hud["hand"])
            hud["complete_valid"] = bool(
                hud["all_hand_valid"]
                and hud["next_card"]["valid"]
                and hud["elixir"]["valid"]
            )
    return dict(counts)


def _contact(occurrences: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    diagnostic = [
        item
        for item in occurrences
        if item["split"] == "same_match_diagnostic" and item.get("glyph_valid")
    ]
    cells = []
    for item in diagnostic:
        glyph = cv2.imread(str(item["glyph_path"]))
        if glyph is None:
            continue
        cell = cv2.cvtColor(cv2.resize(glyph, (128, 128)), cv2.COLOR_BGR2RGB)
        cell = cv2.cvtColor(cell, cv2.COLOR_RGB2BGR)
        canvas: np.ndarray = np.zeros((180, 260, 3), dtype=np.uint8)
        canvas[:128, :128] = cell
        cv2.putText(
            canvas,
            str(item["family"]).split(":", 1)[-1][:18],
            (3, 148),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            f"OCR {item.get('visible_cost', '?')} p{item['player_id']} f{item['frame']}",
            (3, 169),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cells.append(canvas)
    if not cells:
        return {"cells": 0}
    columns = 5
    while len(cells) % columns:
        cells.append(np.zeros_like(cells[0]))
    sheet = np.vstack(
        [
            np.hstack(cells[start : start + columns])
            for start in range(0, len(cells), columns)
        ]
    )
    path = output / "same_match_diagnostic_visible_cost_contact.jpg"
    cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 94])
    return {"cells": len(diagnostic), "path": str(path), "sha256": _sha256(path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--neutral", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--action-labels", type=Path, required=True)
    parser.add_argument("--swift-source", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = _rows(args.neutral)
    occurrences = _occurrences(rows, maximum_per_family=20)
    _extract_glyphs(video=args.video, occurrences=occurrences, output=args.output_dir)
    _ocr(occurrences, args.swift_source, args.output_dir)
    evidence, quarantine = _family_evidence(
        occurrences,
        _cost_authority(args.vocabulary),
        _temporal_costs(args.action_labels),
    )
    rejection_counts = _apply_gate(rows, evidence, quarantine)
    neutral_output = args.output_dir / "neutral_sequence_cost_gated.jsonl.gz"
    _atomic_gzip_jsonl(neutral_output, rows)
    contact = _contact(occurrences, args.output_dir)
    manifest = {
        "schema": SCHEMA,
        "video_sha256": _sha256(args.video),
        "neutral_input_sha256": _sha256(args.neutral),
        "neutral_output": {
            "path": str(neutral_output),
            "sha256": _sha256(neutral_output),
            "rows": len(rows),
        },
        "vocabulary_sha256": _sha256(args.vocabulary),
        "action_labels_sha256": _sha256(args.action_labels),
        "swift_source_sha256": _sha256(args.swift_source),
        "occurrences": occurrences,
        "family_evidence": evidence,
        "quarantined_families": sorted(quarantine),
        "rejection_counts": rejection_counts,
        "same_match_diagnostic_contact": contact,
        "generalization_claim": (
            "none: calibration and diagnostic partitions are temporal slices of one replay; "
            "the promotion gate requires replay-disjoint videos"
        ),
        "inference_contract": (
            "visible cost is current-frame public evidence; whole-match family "
            "aggregation and elixir transitions are offline label-only and never actor input"
        ),
    }
    manifest_path = args.output_dir / "manifest.json"
    _atomic_json(manifest_path, manifest)
    derived_manifest = None
    if args.source_manifest is not None:
        source_manifest_path = args.source_manifest.resolve()
        derived = copy.deepcopy(json.loads(source_manifest_path.read_text()))
        derived["parent_manifest"] = {
            "path": str(source_manifest_path),
            "sha256": _sha256(source_manifest_path),
        }
        derived["artifacts"]["neutral_sequence"] = {
            "path": str(neutral_output.resolve()),
            "sha256": _sha256(neutral_output),
            "rows": len(rows),
        }
        source_events = Path(derived["artifacts"]["offline_play_events"]["path"])
        copied_events = args.output_dir / "offline_play_events_source.json"
        shutil.copy2(source_events, copied_events)
        if _sha256(copied_events) != derived["artifacts"]["offline_play_events"]["sha256"]:
            raise ValueError("offline play event copy hash mismatch")
        derived["artifacts"]["offline_play_events"] = {
            **derived["artifacts"]["offline_play_events"],
            "path": str(copied_events.resolve()),
        }
        derived["visible_cost_gate"] = {
            "manifest": str(manifest_path.resolve()),
            "sha256": _sha256(manifest_path),
            "quarantined_families": sorted(quarantine),
            "rejection_counts": rejection_counts,
            "offline_calibration_evidence_in_actor_records": False,
            "generalization_claim": manifest["generalization_claim"],
        }
        derived_manifest = args.output_dir / "source_manifest_cost_gated.json"
        _atomic_json(derived_manifest, derived)
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "sha256": _sha256(manifest_path),
                "quarantined": sorted(quarantine),
                "rejections": rejection_counts,
                "same_match_diagnostic_contact": contact,
                "source_manifest_cost_gated": (
                    None
                    if derived_manifest is None
                    else {
                        "path": str(derived_manifest),
                        "sha256": _sha256(derived_manifest),
                    }
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
