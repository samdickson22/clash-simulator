from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from clasher.rl.tv_royale_replay import TVRoyalePlacementConverter
from scripts.extract_tv_royale_youtube_fullmatch import (
    HudRecognizer,
    StableIdentityResolver,
    _atomic_json,
)

SCHEMA = "clasher.youtube.reviewed_card_prototype_bank.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reviewed_rows(review_root: Path, sheet_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for review_path in sorted(review_root.glob("*.json")):
        if review_path.name == "index.json":
            continue
        review = json.loads(review_path.read_text(encoding="utf-8"))
        sheet_path = sheet_root / review_path.stem / "manifest.json"
        sheet = json.loads(sheet_path.read_text(encoding="utf-8"))
        if review.get("video_sha256") != sheet.get("video_sha256"):
            raise ValueError(f"review/sheet video mismatch: {review_path.stem}")
        for player_id in (0, 1):
            identities = review["players"][str(player_id)]["card_identities"]
            artifacts = sheet["players"][str(player_id)]["card_artifacts"]
            if len(identities) != 8 or len(artifacts) != 8:
                raise ValueError("reviewed prototype source must expose eight cards")
            for card_index, (identity, artifact) in enumerate(
                zip(identities, artifacts, strict=True)
            ):
                crop_path = Path(artifact["path"])
                if _sha256(crop_path) != artifact["sha256"]:
                    raise ValueError(f"prototype crop hash mismatch: {crop_path}")
                rows.append(
                    {
                        "video_id": review_path.stem,
                        "video_sha256": review["video_sha256"],
                        "player_id": player_id,
                        "card_index": card_index,
                        "identity": str(identity),
                        "crop_path": str(crop_path),
                        "crop_sha256": artifact["sha256"],
                    }
                )
    if not rows:
        raise ValueError("reviewed prototype source is empty")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-root", action="append", type=Path, required=True)
    parser.add_argument("--sheet-root", action="append", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--template-root", type=Path, required=True)
    parser.add_argument("--card-embedding-weight", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--output-arrays", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    args = parser.parse_args()

    if len(args.review_root) != len(args.sheet_root):
        raise ValueError("review and sheet roots must be paired")
    rows = [
        row
        for review_root, sheet_root in zip(
            args.review_root, args.sheet_root, strict=True
        )
        for row in reviewed_rows(review_root, sheet_root)
    ]
    row_keys = [
        (row["video_sha256"], row["player_id"], row["card_index"])
        for row in rows
    ]
    if len(set(row_keys)) != len(row_keys):
        raise ValueError("review sources contain duplicate replay/card rows")
    crops: list[np.ndarray] = []
    for row in rows:
        crop = cv2.imread(row["crop_path"], cv2.IMREAD_COLOR)
        if crop is None:
            raise ValueError("could not decode a reviewed prototype crop")
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
    vectors = recognizer._embed_cards(crops)
    args.output_arrays.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output_arrays,
        vectors=vectors.astype(np.float32),
        labels=np.asarray([row["identity"] for row in rows]),
        video_ids=np.asarray([row["video_id"] for row in rows]),
        crop_sha256s=np.asarray([row["crop_sha256"] for row in rows]),
    )
    manifest = {
        "schema": SCHEMA,
        "rows": len(rows),
        "classes": len({row["identity"] for row in rows}),
        "replay_groups": len({row["video_id"] for row in rows}),
        "arrays": {"path": str(args.output_arrays), "sha256": _sha256(args.output_arrays)},
        "vocabulary_sha256": _sha256(args.vocabulary),
        "card_embedding_weight_sha256": _sha256(args.card_embedding_weight),
        "review_sources": rows,
        "disposition": "candidate_only_pending_broader_replay_disjoint_precision",
    }
    _atomic_json(args.output_manifest, manifest)


if __name__ == "__main__":
    main()
