from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from clasher.rl.card_prototype import complete_unique_deck, prototype_decisions
from clasher.rl.tv_royale_replay import TVRoyalePlacementConverter
from scripts.extract_tv_royale_youtube_fullmatch import (
    HudRecognizer,
    StableIdentityResolver,
    _atomic_json,
)

SCHEMA = "clasher.youtube.eight_card_prototype_classification.v1"
MINIMUM_SCORE = 0.92
MINIMUM_MARGIN = 0.02


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet-manifest", type=Path, required=True)
    parser.add_argument("--bank-manifest", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--template-root", type=Path, required=True)
    parser.add_argument("--card-embedding-weight", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sheet = json.loads(args.sheet_manifest.read_text(encoding="utf-8"))
    bank_manifest = json.loads(args.bank_manifest.read_text(encoding="utf-8"))
    if bank_manifest.get("schema") != "clasher.youtube.reviewed_card_prototype_bank.v1":
        raise ValueError("unsupported prototype bank")
    arrays_path = Path(bank_manifest["arrays"]["path"])
    if _sha256(arrays_path) != bank_manifest["arrays"]["sha256"]:
        raise ValueError("prototype bank hash mismatch")
    bank = np.load(arrays_path, allow_pickle=False)
    prototypes = np.asarray(bank["vectors"], dtype=np.float32)
    labels = [str(value) for value in bank["labels"]]

    crop_paths: list[Path] = []
    for player_id in (0, 1):
        artifacts = sheet["players"][str(player_id)]["card_artifacts"]
        if len(artifacts) != 8:
            raise ValueError("deck sheet must expose eight cards per player")
        for artifact in artifacts:
            path = Path(artifact["path"])
            if _sha256(path) != artifact["sha256"]:
                raise ValueError(f"deck crop hash mismatch: {path}")
            crop_paths.append(path)
    crops: list[np.ndarray] = []
    for path in crop_paths:
        crop = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if crop is None:
            raise ValueError("could not decode deck crop")
        crops.append(crop)
    resolver = StableIdentityResolver(
        args.vocabulary.resolve(), TVRoyalePlacementConverter(source_frame_hz=10.0)
    )
    recognizer = HudRecognizer(
        args.template_root.resolve(),
        resolver,
        device=args.device,
        card_weight_path=args.card_embedding_weight.resolve(),
        card_preprocess_backend="tensor",
        card_preprocess_workers=2,
    )
    queries = recognizer._embed_cards(crops)
    decisions = prototype_decisions(
        queries,
        prototypes,
        labels,
        minimum_score=MINIMUM_SCORE,
        minimum_margin=MINIMUM_MARGIN,
    )
    players = {}
    for player_id in (0, 1):
        rows = decisions[player_id * 8 : (player_id + 1) * 8]
        players[str(player_id)] = {
            "cards": [row.__dict__ for row in rows],
            "candidate_closed": complete_unique_deck(rows),
        }
    payload = {
        "schema": SCHEMA,
        "video_id": sheet["video_id"],
        "video_sha256": sheet["video_sha256"],
        "sheet_manifest_sha256": _sha256(args.sheet_manifest),
        "bank_manifest_sha256": _sha256(args.bank_manifest),
        "thresholds": {"minimum_score": MINIMUM_SCORE, "minimum_margin": MINIMUM_MARGIN},
        "players": players,
        "candidate_match_closed": all(
            players[str(player_id)]["candidate_closed"] for player_id in (0, 1)
        ),
        "training_eligible": False,
        "disposition": "candidate_only_pending_broader_replay_disjoint_precision",
    }
    _atomic_json(args.output, payload)


if __name__ == "__main__":
    main()
