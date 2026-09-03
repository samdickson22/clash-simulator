from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "reports" / "hog26_procedural_outcome_protocol_seed1278401.json"


def test_procedural_outcome_protocol_is_split_safe_and_pinned() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    for authority in ("base_policy", "procedural_decks", "original_decks"):
        row = protocol[authority]
        path = ROOT / row["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]

    manifest = json.loads((ROOT / protocol["procedural_decks"]["path"]).read_text())
    actual_families: dict[str, set[str]] = {}
    for row in manifest["decks"]:
        if row.get("family_id") is not None:
            actual_families.setdefault(row["split"], set()).add(row["family_id"])

    train_rows = protocol["training"]
    train_families = set(train_rows[0]["family_ids"])
    assert all(set(row["family_ids"]) == train_families for row in train_rows)
    assert train_families == actual_families["train"]
    selection = set(protocol["development_selection"]["family_ids"])
    calibration = set(protocol["probability_calibration"]["family_ids"])
    holdout = set(protocol["final_holdout"]["generated"]["family_ids"])
    assert selection | calibration == actual_families["development"]
    assert holdout == actual_families["holdout"]
    assert not selection & calibration
    assert not train_families & (selection | calibration | holdout)
    assert not (selection | calibration) & holdout

    seeds = [row["seed"] for row in train_rows]
    seeds.extend(
        [
            protocol["development_selection"]["seed"],
            protocol["probability_calibration"]["seed"],
            protocol["final_holdout"]["generated"]["seed"],
            protocol["final_holdout"]["reserved_original"]["seed"],
        ]
    )
    assert len(seeds) == len(set(seeds))
    train_opponents = {opponent for row in train_rows for opponent in row["opponents"]}
    assert "split-lane" not in train_opponents
    assert protocol["final_holdout"]["generated"]["opponents"] == ["split-lane"]
    assert protocol["final_holdout"]["reserved_original"]["opponents"] == [
        "split-lane"
    ]
