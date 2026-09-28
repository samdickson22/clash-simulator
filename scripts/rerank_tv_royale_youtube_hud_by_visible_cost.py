from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import copy
import gzip
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from clasher.rl.tv_royale_replay import TVRoyalePlacementConverter
from scripts.build_tv_royale_youtube_visible_cost_gate import _cost_box, _digit_glyph
from scripts.extract_tv_royale_youtube_fullmatch import (
    HudRecognizer,
    StableIdentityResolver,
    _atomic_gzip_jsonl,
    _atomic_json,
    _crop_relative,
    _sha256,
)

SCHEMA = "clasher.youtube.visible_cost_conditioned_hud.v1"


def _rows(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _cost_authority(vocabulary: Path) -> dict[str, int]:
    payload = json.loads(vocabulary.read_text())
    return {
        str(row["stable_key"]): int(row["mana_cost"])
        for row in payload["entries"]
        if row["namespace"] == "card_action"
        and isinstance(row.get("mana_cost"), int | float)
    }


def _glyph_vector(glyph: np.ndarray) -> np.ndarray:
    resized = cv2.resize(glyph, (32, 32), interpolation=cv2.INTER_NEAREST)
    return np.asarray(resized > 127, dtype=np.bool_)


def _fixed_position_digit_glyph(image: np.ndarray) -> np.ndarray | None:
    """Extract the white cost numeral even when the card is grayscale."""

    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    white = ((hsv[:, :, 2] > 145) & (hsv[:, :, 1] < 120)).astype(np.uint8) * 255
    count, _, stats, _ = cv2.connectedComponentsWithStats(white)
    candidates: list[tuple[float, int]] = []
    for component in range(1, count):
        x, y, box_width, box_height, area = stats[component]
        center_x = (x + box_width * 0.5) / width
        center_y = (y + box_height * 0.5) / height
        aspect = box_width / max(1, box_height)
        if not (
            0.25 <= center_x <= 0.85
            and 0.63 <= center_y <= 0.93
            and 0.05 <= box_height / height <= 0.22
            and 0.02 <= box_width / width <= 0.22
            and 0.15 <= aspect <= 1.5
            and area >= 10
        ):
            continue
        score = float(area) * (1.0 - abs(center_y - 0.80))
        candidates.append((score, component))
    if not candidates:
        return None
    _, component = max(candidates)
    x, y, box_width, box_height, _ = stats[component]
    glyph = white[y : y + box_height, x : x + box_width]
    canvas = np.full((128, 128), 255, dtype=np.uint8)
    scale = min(90 / box_width, 90 / box_height)
    resized_width = max(1, round(box_width * scale))
    resized_height = max(1, round(box_height * scale))
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


class VisibleCostClassifier:
    def __init__(self, calibration_manifest: Path) -> None:
        payload = json.loads(calibration_manifest.read_text())
        self.quarantined_families = set(payload.get("quarantined_families", []))
        self.rows: list[tuple[int, np.ndarray]] = []
        for row in payload["occurrences"]:
            if row.get("split") != "calibration" or not row.get("ocr_valid"):
                continue
            glyph = cv2.imread(str(row["glyph_path"]), cv2.IMREAD_GRAYSCALE)
            if glyph is not None:
                self.rows.append((int(row["visible_cost"]), _glyph_vector(glyph)))
        if not self.rows:
            raise ValueError("visible-cost calibration has no valid glyphs")

    def classify(self, crop: np.ndarray) -> dict[str, Any]:
        glyph = _digit_glyph(cv2.resize(crop, None, fx=3.0, fy=3.0))
        glyph_source = "color_badge"
        if glyph is None:
            glyph = _fixed_position_digit_glyph(crop)
            glyph_source = "fixed_position_white_numeral"
        if glyph is None:
            return {
                "value": None,
                "valid": False,
                "confidence": 0.0,
                "reason": "current_frame_cost_glyph_not_visible",
                "evidence": "current_frame_printed_card_cost",
            }
        query = _glyph_vector(glyph)
        scores: list[tuple[float, int]] = []
        for cost, reference in self.rows:
            union = int(np.count_nonzero(query | reference))
            intersection = int(np.count_nonzero(query & reference))
            scores.append((intersection / union if union else 0.0, cost))
        scores.sort(reverse=True)
        best_score, best_cost = scores[0]
        runner = max(
            (score for score, cost in scores if cost != best_cost), default=0.0
        )
        valid = best_score >= 0.90 and best_score - runner >= 0.05
        return {
            "value": best_cost if valid else None,
            "candidate": best_cost,
            "valid": valid,
            "confidence": best_score,
            "runner_up_confidence": runner,
            "margin": best_score - runner,
            "reason": None if valid else "uncalibrated_or_ambiguous_cost_glyph",
            "evidence": "current_frame_printed_card_cost",
            "glyph_source": glyph_source,
        }


def _family_scores(hud: HudRecognizer, crops: list[np.ndarray]) -> list[dict[str, float]]:
    scores = hud._embed_cards(crops) @ hud.card_vectors.T
    output: list[dict[str, float]] = []
    for score_row in scores:
        family_scores: dict[str, float] = {}
        for score, family in zip(score_row, hud.card_families, strict=True):
            family_scores[family] = max(
                family_scores.get(family, -1.0), float(score)
            )
        output.append(family_scores)
    return output


def _decision(
    family_scores: dict[str, float],
    displayed_cost: dict[str, Any],
    cost_authority: dict[str, int],
    *,
    is_next: bool,
    unsupported_families: set[str],
) -> dict[str, Any]:
    all_ranked = sorted(family_scores.items(), key=lambda item: item[1], reverse=True)
    overall_candidate = all_ranked[0][0]
    visible_cost = displayed_cost.get("value") if displayed_cost.get("valid") else None
    if isinstance(visible_cost, int):
        ranked = [
            item for item in all_ranked if cost_authority.get(item[0]) == visible_cost
        ]
        evidence = "current_frame_embedding_reranked_by_current_frame_printed_cost"
    else:
        ranked = all_ranked
        evidence = "current_frame_embedding_cost_unavailable"
    if not ranked:
        return {
            "value": None,
            "candidate": None,
            "score": 0.0,
            "runner_up_score": 0.0,
            "margin": 0.0,
            "valid": False,
            "reason": "no_card_candidate_matches_visible_cost",
            "displayed_cost": displayed_cost,
            "evidence": evidence,
        }
    candidate, score = ranked[0]
    if overall_candidate in unsupported_families:
        return {
            "value": None,
            "candidate": candidate,
            "score": score,
            "runner_up_score": ranked[1][1] if len(ranked) > 1 else -1.0,
            "margin": 0.0,
            "valid": False,
            "reason": "current_client_hero_or_variant_art_not_in_template_authority",
            "displayed_cost": displayed_cost,
            "evidence": evidence,
        }
    runner = ranked[1][1] if len(ranked) > 1 else -1.0
    margin = score - runner
    minimum = 0.70 if is_next else 0.72
    valid = score >= minimum and margin >= 0.035
    return {
        "value": candidate if valid else None,
        "candidate": candidate,
        "score": score,
        "runner_up_score": runner,
        "margin": margin,
        "valid": valid,
        "reason": None if valid else "uncalibrated_or_ambiguous_cost_conditioned_match",
        "displayed_cost": displayed_cost,
        "evidence": evidence,
    }


def _decorate_hud(
    hud: dict[str, Any], cost_authority: dict[str, int]
) -> dict[str, Any]:
    elixir = hud["elixir"]
    value = elixir.get("value") if elixir.get("valid") else None
    elixir["fractional_value"] = value
    elixir["integer_floor"] = math.floor(value) if isinstance(value, int | float) else None
    elixir["fractional_fill_valid"] = bool(elixir.get("valid"))
    for head in hud["hand"]:
        card = head.get("value") if head.get("valid") else None
        cost = cost_authority.get(card) if isinstance(card, str) else None
        head["affordability"] = {
            "value": (
                bool(float(value) + 1e-6 >= cost)
                if isinstance(value, int | float) and cost is not None
                else None
            ),
            "valid": isinstance(value, int | float) and cost is not None,
            "evidence": "current_frame_own_elixir_and_public_card_cost",
        }
        head["evolution"] = {
            "progress": None,
            "ready": None,
            "valid": False,
            "reason": "evolution_hud_head_not_calibrated",
        }
        head["unaffordable_visual"] = {
            "value": None,
            "valid": False,
            "reason": "grayscale_state_head_not_calibrated",
        }
    hud["next_card"]["evolution"] = {
        "progress": None,
        "ready": None,
        "valid": False,
        "reason": "evolution_hud_head_not_calibrated",
    }
    hud["all_hand_valid"] = all(head["valid"] for head in hud["hand"])
    hud["complete_valid"] = bool(
        hud["all_hand_valid"] and hud["next_card"]["valid"] and elixir["valid"]
    )
    return hud


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--neutral", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--cost-calibration-manifest", type=Path, required=True)
    parser.add_argument(
        "--template-root",
        type=Path,
        default=Path("datasets/external/CS541-Deep-Learning-Clash-Royale-Project"),
    )
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    rows = _rows(args.neutral.resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    vocabulary = args.vocabulary.resolve()
    cost_authority = _cost_authority(vocabulary)
    resolver = StableIdentityResolver(
        vocabulary, TVRoyalePlacementConverter(source_frame_hz=10.0)
    )
    hud = HudRecognizer(
        args.template_root.resolve(), resolver, device=args.device, card_weight_path=None
    )
    cost_classifier = VisibleCostClassifier(args.cost_calibration_manifest.resolve())

    capture = cv2.VideoCapture(str(args.video.resolve()))
    source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    if source_fps <= 0:
        raise ValueError("video FPS is unavailable")
    batch_indices: list[int] = []
    batch_crops: list[np.ndarray] = []
    batch_costs: list[dict[str, Any]] = []
    evidence_rows: dict[int, dict[str, Any]] = {}

    def flush() -> None:
        if not batch_indices:
            return
        score_rows = _family_scores(hud, batch_crops)
        cursor = 0
        for row_index in batch_indices:
            record_evidence: dict[str, Any] = {"0": [], "1": []}
            for player_id in (0, 1):
                decisions = []
                for slot in range(5):
                    scores = score_rows[cursor]
                    displayed_cost = batch_costs[cursor]
                    decisions.append(
                        _decision(
                            scores,
                            displayed_cost,
                            cost_authority,
                            is_next=slot == 4,
                            unsupported_families=cost_classifier.quarantined_families,
                        )
                    )
                    record_evidence[str(player_id)].append(
                        {
                            "slot": "next" if slot == 4 else slot,
                            "family_scores": scores,
                            "displayed_cost": displayed_cost,
                        }
                    )
                    cursor += 1
                rows[row_index]["offline_privileged_hud"][str(player_id)] = _decorate_hud(
                    {
                        "hand": decisions[:4],
                        "next_card": decisions[4],
                        "elixir": copy.deepcopy(
                            rows[row_index]["offline_privileged_hud"][str(player_id)][
                                "elixir"
                            ]
                        ),
                    },
                    cost_authority,
                )
            evidence_rows[row_index] = record_evidence
        batch_indices.clear()
        batch_crops.clear()
        batch_costs.clear()

    source_frame_index = -1
    frame: np.ndarray | None = None
    for row_index in range(len(rows)):
        target_source_frame = round(row_index * source_fps / 10.0)
        while source_frame_index < target_source_frame:
            ok, next_frame = capture.read()
            if not ok:
                raise ValueError(f"could not decode HUD frame {row_index}")
            frame = next_frame
            source_frame_index += 1
        if frame is None:
            raise ValueError("video yielded no frames")
        prepared = hud.prepare_frame(frame)
        batch_indices.append(row_index)
        for player_id in (0, 1):
            for slot, crop in enumerate(prepared[player_id]["card_crops"]):
                batch_crops.append(crop)
                cost_crop = (
                    _crop_relative(frame, _cost_box(player_id, slot))
                    if slot < 4
                    else crop
                )
                batch_costs.append(cost_classifier.classify(cost_crop))
        if len(batch_indices) >= args.batch_size:
            flush()
    flush()
    capture.release()

    evidence_path = args.output_dir / "offline_full_hud_candidate_scores.jsonl.gz"
    _atomic_gzip_jsonl(
        evidence_path,
        [
            {
                "schema": SCHEMA,
                "snapshot_id": rows[index]["snapshot_id"],
                "timestamp_ms": rows[index]["timestamp_ms"],
                "players": evidence_rows[index],
                "offline_extractor_only": True,
                "actor_input": False,
            }
            for index in range(len(rows))
        ],
    )
    neutral_path = args.output_dir / "neutral_sequence_cost_conditioned.jsonl.gz"
    _atomic_gzip_jsonl(neutral_path, rows)

    source_manifest_path = args.source_manifest.resolve()
    source_manifest = json.loads(source_manifest_path.read_text())
    source_manifest["parent_manifest"] = {
        "path": str(source_manifest_path),
        "sha256": _sha256(source_manifest_path),
    }
    source_manifest["artifacts"]["neutral_sequence"] = {
        "path": str(neutral_path.resolve()),
        "sha256": _sha256(neutral_path),
        "rows": len(rows),
    }
    source_manifest["visible_cost_conditioned_hud"] = {
        "schema": SCHEMA,
        "offline_candidate_scores": {
            "path": str(evidence_path.resolve()),
            "sha256": _sha256(evidence_path),
            "rows": len(rows),
            "actor_input": False,
        },
        "calibration_scope": "same_replay_diagnostic_only",
        "replay_disjoint_promotion_ready": False,
        "selected_hud_results_use_current_frame_evidence_only": True,
    }
    derived_manifest = args.output_dir / "source_manifest_cost_conditioned.json"
    _atomic_json(derived_manifest, source_manifest)

    counts: Counter[str] = Counter()
    for row in rows:
        for player_id in (0, 1):
            hud_row = row["offline_privileged_hud"][str(player_id)]
            counts[f"p{player_id}_complete"] += int(hud_row["complete_valid"])
            counts[f"p{player_id}_hand_valid"] += sum(
                head["valid"] for head in hud_row["hand"]
            )
            counts[f"p{player_id}_next_valid"] += int(hud_row["next_card"]["valid"])
            counts[f"p{player_id}_cost_valid"] += sum(
                head["displayed_cost"]["valid"]
                for head in [*hud_row["hand"], hud_row["next_card"]]
            )
        counts["simultaneous_complete"] += int(
            all(
                row["offline_privileged_hud"][str(player_id)]["complete_valid"]
                for player_id in (0, 1)
            )
        )
    manifest = {
        "schema": SCHEMA,
        "video_sha256": _sha256(args.video),
        "neutral_input_sha256": _sha256(args.neutral),
        "neutral_output": {
            "path": str(neutral_path.resolve()),
            "sha256": _sha256(neutral_path),
            "rows": len(rows),
        },
        "offline_candidate_scores": {
            "path": str(evidence_path.resolve()),
            "sha256": _sha256(evidence_path),
        },
        "derived_source_manifest": {
            "path": str(derived_manifest.resolve()),
            "sha256": _sha256(derived_manifest),
        },
        "vocabulary_sha256": _sha256(vocabulary),
        "cost_calibration_manifest_sha256": _sha256(args.cost_calibration_manifest),
        "calibration_scope": "same_replay_diagnostic_only",
        "replay_disjoint_promotion_ready": False,
        "counts": dict(sorted(counts.items())),
        "elapsed_seconds": time.perf_counter() - started,
        "inference_contract": {
            "actor_hud_contains_current_frame_selected_results_only": True,
            "full_candidate_scores_offline_only": True,
            "next_rotation_and_elixir_transitions_used_for_reranking": False,
            "opponent_hud_excluded_by_actor_projection": True,
        },
    }
    manifest_path = args.output_dir / "manifest.json"
    _atomic_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "sha256": _sha256(manifest_path),
                "counts": manifest["counts"],
                "elapsed_seconds": manifest["elapsed_seconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
