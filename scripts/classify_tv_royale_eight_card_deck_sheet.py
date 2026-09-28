from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from pathlib import Path
from typing import Any

import cv2

from clasher.rl.tv_royale_replay import TVRoyalePlacementConverter
from scripts.extract_tv_royale_youtube_fullmatch import (
    HudRecognizer,
    StableIdentityResolver,
    _atomic_json,
    _sha256,
)
from scripts.rerank_tv_royale_youtube_hud_by_visible_cost import (
    VisibleCostClassifier,
    _cost_authority,
    _decision,
    _family_scores,
)

SCHEMA = "clasher.youtube.eight_card_deck_classification.v1"
CELL_WIDTH = 180
CELL_HEIGHT = 235
LABEL_HEIGHT = 34
MINIMUM_AUTO_SCORE = 0.80
MINIMUM_AUTO_MARGIN = 0.06


def auto_close_player(rows: list[dict[str, Any]]) -> bool:
    identities = [row.get("identity") for row in rows]
    return bool(
        len(rows) == 8
        and all(row.get("auto_valid") for row in rows)
        and len(set(identities)) == 8
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet-manifest", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--cost-calibration-manifest", type=Path, required=True)
    parser.add_argument("--template-root", type=Path, required=True)
    parser.add_argument("--card-embedding-weight", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sheet_manifest = json.loads(args.sheet_manifest.read_text(encoding="utf-8"))
    if sheet_manifest.get("schema") != "clasher.youtube.eight_card_deck_sheet.v1":
        raise ValueError("unsupported eight-card sheet manifest")
    sheet_path = Path(sheet_manifest["artifact"]["path"])
    if _sha256(sheet_path) != sheet_manifest["artifact"]["sha256"]:
        raise ValueError("deck sheet hash mismatch")
    sheet = cv2.imread(str(sheet_path), cv2.IMREAD_COLOR)
    if sheet is None or sheet.shape[:2] != (CELL_HEIGHT * 2, CELL_WIDTH * 8):
        raise ValueError("unexpected deck sheet geometry")
    crops = []
    for player_id in (0, 1):
        artifacts = sheet_manifest["players"][str(player_id)].get("card_artifacts")
        if not isinstance(artifacts, list) or len(artifacts) != 8:
            raise ValueError("deck sheet lacks eight lossless card artifacts")
        for artifact in artifacts:
            path = Path(artifact["path"])
            if _sha256(path) != artifact["sha256"]:
                raise ValueError("deck card artifact hash mismatch")
            crop = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if crop is None:
                raise ValueError(f"could not read deck card crop {path}")
            crops.append(crop)

    vocabulary = args.vocabulary.resolve()
    resolver = StableIdentityResolver(
        vocabulary, TVRoyalePlacementConverter(source_frame_hz=10.0)
    )
    recognizer = HudRecognizer(
        args.template_root.resolve(),
        resolver,
        device=args.device,
        card_weight_path=args.card_embedding_weight.resolve(),
        card_preprocess_backend="tensor",
        card_preprocess_workers=2,
    )
    cost_classifier = VisibleCostClassifier(args.cost_calibration_manifest.resolve())
    cost_authority = _cost_authority(vocabulary)
    scores = _family_scores(recognizer, crops)
    costs = [cost_classifier.classify(crop) for crop in crops]
    unsupported = cost_classifier.quarantined_families

    players: dict[str, Any] = {}
    for player_id in (0, 1):
        rows: list[dict[str, Any]] = []
        for card_index in range(8):
            flat_index = player_id * 8 + card_index
            decision = _decision(
                scores[flat_index],
                costs[flat_index],
                cost_authority,
                is_next=card_index >= 4,
                unsupported_families=unsupported,
            )
            identity = decision.get("value") if decision.get("valid") else None
            auto_valid = bool(
                identity is not None
                and costs[flat_index].get("valid")
                and float(decision["score"]) >= MINIMUM_AUTO_SCORE
                and float(decision["margin"]) >= MINIMUM_AUTO_MARGIN
            )
            rows.append(
                {
                    "card_index": card_index,
                    "source": "initial_hand" if card_index < 4 else "queue_reveal",
                    "identity": identity,
                    "candidate": decision.get("candidate"),
                    "score": decision.get("score"),
                    "margin": decision.get("margin"),
                    "printed_cost": costs[flat_index],
                    "auto_valid": auto_valid,
                    "reason": None if auto_valid else decision.get("reason") or "strict_auto_gate_failed",
                }
            )
        players[str(player_id)] = {
            "cards": rows,
            "auto_closed": auto_close_player(rows),
        }

    payload = {
        "schema": SCHEMA,
        "video_id": sheet_manifest["video_id"],
        "video_sha256": sheet_manifest["video_sha256"],
        "sheet_manifest": {
            "path": str(args.sheet_manifest.resolve()),
            "sha256": _sha256(args.sheet_manifest),
        },
        "vocabulary_sha256": _sha256(vocabulary),
        "cost_calibration_sha256": _sha256(args.cost_calibration_manifest),
        "card_embedding_weight_sha256": _sha256(args.card_embedding_weight),
        "thresholds": {
            "minimum_auto_score": MINIMUM_AUTO_SCORE,
            "minimum_auto_margin": MINIMUM_AUTO_MARGIN,
            "printed_cost_required": True,
            "eight_unique_identities_required": True,
        },
        "players": players,
        "status": (
            "auto_closed"
            if all(players[str(player_id)]["auto_closed"] for player_id in (0, 1))
            else "manual_review_required"
        ),
    }
    _atomic_json(args.output, payload)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "status": payload["status"],
                "auto_valid_cards": sum(
                    row["auto_valid"]
                    for player in players.values()
                    for row in player["cards"]
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
