"""Add strictly calibrated video-crop prototypes without promoting labels."""

# mypy: disable-error-code="import-untyped"
from __future__ import annotations

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

SCHEMA = "clasher.youtube.reviewed_plus_strict_pseudo_card_prototype_bank.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_pseudo_rows(
    *,
    base_manifest: Path,
    classification_root: Path,
    sheet_root: Path,
    minimum_score: float,
    minimum_margin: float,
) -> list[dict[str, Any]]:
    if not 0.0 <= minimum_score <= 1.0 or not 0.0 <= minimum_margin <= 1.0:
        raise ValueError("strict pseudo thresholds must be in [0, 1]")
    base_sha = _sha256(base_manifest)
    base = json.loads(base_manifest.read_text(encoding="utf-8"))
    reviewed_videos = {
        str(row["video_sha256"]) for row in base.get("review_sources", ())
    }
    rows: list[dict[str, Any]] = []
    seen_crops: set[str] = set()
    for classification_path in sorted(classification_root.glob("*.json")):
        classification = json.loads(
            classification_path.read_text(encoding="utf-8")
        )
        if classification.get("bank_manifest_sha256") != base_sha:
            continue
        if str(classification.get("video_sha256")) in reviewed_videos:
            continue
        video_id = str(classification["video_id"])
        sheet_path = sheet_root / video_id / "manifest.json"
        sheet = json.loads(sheet_path.read_text(encoding="utf-8"))
        if sheet.get("video_sha256") != classification.get("video_sha256"):
            raise ValueError("classification and sheet video digests differ")
        for player_id in (0, 1):
            decisions = classification["players"][str(player_id)]["cards"]
            artifacts = sheet["players"][str(player_id)]["card_artifacts"]
            if len(decisions) != 8 or len(artifacts) != 8:
                raise ValueError("strict pseudo source must retain eight card rows")
            for card_index, (decision, artifact) in enumerate(
                zip(decisions, artifacts, strict=True)
            ):
                score = float(decision["score"])
                margin = float(decision["margin"])
                if score < minimum_score or margin < minimum_margin:
                    continue
                crop_path = Path(artifact["path"])
                crop_sha = str(artifact["sha256"])
                if _sha256(crop_path) != crop_sha:
                    raise ValueError("strict pseudo crop hash mismatch")
                if crop_sha in seen_crops:
                    continue
                seen_crops.add(crop_sha)
                rows.append(
                    {
                        "video_id": video_id,
                        "video_sha256": classification["video_sha256"],
                        "player_id": player_id,
                        "card_index": card_index,
                        "identity": str(decision["candidate"]),
                        "score": score,
                        "margin": margin,
                        "crop_path": str(crop_path),
                        "crop_sha256": crop_sha,
                    }
                )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-bank-manifest", type=Path, required=True)
    parser.add_argument("--classification-root", type=Path, required=True)
    parser.add_argument("--sheet-root", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--template-root", type=Path, required=True)
    parser.add_argument("--card-embedding-weight", type=Path, required=True)
    parser.add_argument("--minimum-score", type=float, default=0.92)
    parser.add_argument("--minimum-margin", type=float, default=0.15)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--output-arrays", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    args = parser.parse_args()

    base_manifest = json.loads(
        args.base_bank_manifest.read_text(encoding="utf-8")
    )
    base_arrays_path = Path(base_manifest["arrays"]["path"])
    if _sha256(base_arrays_path) != base_manifest["arrays"]["sha256"]:
        raise ValueError("base prototype bank hash mismatch")
    with np.load(base_arrays_path, allow_pickle=False) as source:
        base_vectors = np.asarray(source["vectors"], dtype=np.float32)
        base_labels = np.asarray(source["labels"]).astype(str)
        base_video_ids = np.asarray(source["video_ids"]).astype(str)
        base_crop_sha256s = np.asarray(source["crop_sha256s"]).astype(str)
    pseudo = strict_pseudo_rows(
        base_manifest=args.base_bank_manifest,
        classification_root=args.classification_root,
        sheet_root=args.sheet_root,
        minimum_score=args.minimum_score,
        minimum_margin=args.minimum_margin,
    )
    if not pseudo:
        raise ValueError("strict pseudo source produced no rows")
    crops: list[np.ndarray] = []
    for row in pseudo:
        crop = cv2.imread(row["crop_path"], cv2.IMREAD_COLOR)
        if crop is None:
            raise ValueError("could not decode strict pseudo crop")
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
    pseudo_vectors = recognizer._embed_cards(crops).astype(np.float32)
    output_vectors = np.concatenate((base_vectors, pseudo_vectors), axis=0)
    output_labels = np.concatenate(
        (base_labels, np.asarray([row["identity"] for row in pseudo]))
    )
    output_video_ids = np.concatenate(
        (base_video_ids, np.asarray([row["video_id"] for row in pseudo]))
    )
    output_crop_sha256s = np.concatenate(
        (
            base_crop_sha256s,
            np.asarray([row["crop_sha256"] for row in pseudo]),
        )
    )
    args.output_arrays.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output_arrays,
        vectors=output_vectors,
        labels=output_labels,
        video_ids=output_video_ids,
        crop_sha256s=output_crop_sha256s,
    )
    payload = {
        "schema": SCHEMA,
        "base_bank": {
            "path": str(args.base_bank_manifest),
            "sha256": _sha256(args.base_bank_manifest),
            "rows": int(base_vectors.shape[0]),
        },
        "strict_thresholds": {
            "minimum_score": args.minimum_score,
            "minimum_margin": args.minimum_margin,
        },
        "pseudo_rows": len(pseudo),
        "pseudo_replay_groups": len({row["video_sha256"] for row in pseudo}),
        "rows": int(output_vectors.shape[0]),
        "classes": len(set(output_labels.tolist())),
        "arrays": {
            "path": str(args.output_arrays),
            "sha256": _sha256(args.output_arrays),
        },
        "pseudo_sources": pseudo,
        "disposition": (
            "candidate_only_self_training_pending_untouched_replay_validation"
        ),
        "training_eligible": False,
    }
    _atomic_json(args.output_manifest, payload)
    print(json.dumps({key: payload[key] for key in ("rows", "classes", "pseudo_rows", "pseudo_replay_groups")}, indent=2))


if __name__ == "__main__":
    main()
