from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.extract_tv_royale_youtube_fullmatch import _atomic_json, _sha256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    labels = json.loads(args.labels.read_text())
    review = json.loads(args.review.read_text())
    if _sha256(args.labels) != review["labels_sha256"]:
        raise ValueError("review does not match action-label artifact")
    rows = labels["labels"]
    if len(rows) != review["reviewed_candidate_count"]:
        raise ValueError("reviewed candidate count does not match")
    rejected_plays = set(review["rejected_play_label_ids"])
    rejected_identities = set(review["rejected_identity_label_ids"])
    rejected_placements = set(review["rejected_placement_label_ids"])
    identity_overrides = review.get("identity_overrides", {})
    gold: list[dict[str, Any]] = []
    for row in rows:
        label_id = str(row["label_id"])
        play_valid = label_id not in rejected_plays
        override_identity = identity_overrides.get(label_id)
        identity_valid = bool(
            play_valid
            and label_id not in rejected_identities
            and (row["identity_valid"] or isinstance(override_identity, str))
        )
        placement_valid = bool(
            play_valid and row["placement_valid"] and label_id not in rejected_placements
        )
        gold.append(
            {
                "label_id": label_id,
                "player_id": row["player_id"],
                "timestamp_ms": row["timestamp_ms"],
                "play_valid": play_valid,
                "identity_valid": identity_valid,
                "card_identity": (
                    override_identity
                    if isinstance(override_identity, str)
                    else row["card_identity"] if identity_valid else None
                ),
                "placement_valid": placement_valid,
                "deployment_tile_absolute": (
                    row["deployment_tile_absolute"] if placement_valid else None
                ),
                "annotation": "manual_visual_confirmation",
            }
        )
    payload = {
        "schema": "clasher.youtube.action_gold.v1",
        "match_id": review["match_id"],
        "labels_source": {
            "path": str(args.labels.resolve()),
            "sha256": _sha256(args.labels),
        },
        "review_source": {
            "path": str(args.review.resolve()),
            "sha256": _sha256(args.review),
        },
        "annotation_scope": review["annotation_scope"],
        "generalization_claim": "none; one replay and candidate-conditioned visual review",
        "recall_audit": review["recall_audit"],
        "labels": gold,
    }
    _atomic_json(args.output, payload)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": _sha256(args.output),
                "plays": sum(row["play_valid"] for row in gold),
                "identities": sum(row["identity_valid"] for row in gold),
                "placements": sum(row["placement_valid"] for row in gold),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
