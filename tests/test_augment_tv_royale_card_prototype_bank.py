from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.augment_tv_royale_card_prototype_bank import strict_pseudo_rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_strict_pseudo_rows_require_pinned_bank_and_margin(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    base.write_text(json.dumps({"review_sources": []}), encoding="utf-8")
    classifications = tmp_path / "classifications"
    sheets = tmp_path / "sheets"
    classifications.mkdir()
    (sheets / "video").mkdir(parents=True)
    crops = []
    artifacts = []
    decisions = []
    for index in range(8):
        crop = sheets / "video" / f"{index}.png"
        crop.write_bytes(f"crop-{index}".encode())
        crops.append(crop)
        artifacts.append({"path": str(crop), "sha256": _sha256(crop)})
        decisions.append(
            {
                "candidate": f"card:{index}",
                "score": 0.99,
                "margin": 0.20 if index == 0 else 0.10,
            }
        )
    sheet = {
        "video_sha256": "v" * 64,
        "players": {
            "0": {"card_artifacts": artifacts},
            "1": {"card_artifacts": artifacts},
        },
    }
    (sheets / "video" / "manifest.json").write_text(json.dumps(sheet))
    classification = {
        "video_id": "video",
        "video_sha256": "v" * 64,
        "bank_manifest_sha256": _sha256(base),
        "players": {
            "0": {"cards": decisions},
            "1": {"cards": decisions},
        },
    }
    (classifications / "video.json").write_text(json.dumps(classification))

    rows = strict_pseudo_rows(
        base_manifest=base,
        classification_root=classifications,
        sheet_root=sheets,
        minimum_score=0.92,
        minimum_margin=0.15,
    )

    assert len(rows) == 1
    assert rows[0]["card_index"] == 0
    assert rows[0]["identity"] == "card:0"

