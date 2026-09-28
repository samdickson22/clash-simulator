from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "reports/hog26_flat_median_counterfactual_quarantine_contract_v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fresh_counterfactual_quarantine_pins_sources_and_unseen_decks() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["status"] == "ready"
    assert contract["promotion_authorized"] is False
    for entry in contract["sources"].values():
        path = ROOT / entry["path"]
        assert _sha256(path) == entry["sha256"]

    pool = json.loads(
        (ROOT / contract["sources"]["opponent_decks"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    assert pool["schema"] == "clasher.hog26_counterfactual_quarantine_pool.v1"
    assert set(pool["archetype_deck_counts"]) == {
        "graveyard",
        "lava-hound",
        "royal-hogs",
        "x-bow",
    }
    assert all(
        abs(float(value) - 0.25) < 1e-12
        for value in pool["archetype_weight_sums"].values()
    )
    quarantine = {tuple(sorted(row["cards"])) for row in pool["decks"]}
    previous = set()
    for split in ("train", "validation"):
        report = json.loads(
            (
                ROOT
                / "datasets/derived/hog26_phase_balanced_terminal_cf_v3_seed1175001"
                / f"{split}.json"
            ).read_text(encoding="utf-8")
        )
        for game in report["games"]:
            controlled = int(game["controlled_player"])
            previous.add(tuple(sorted(game["decks"][1 - controlled])))
    for phase in ("screen", "quarantine"):
        root = ROOT / "reports/hog26_phase_balanced_flat_median_dev_v1/gameplay" / phase
        for path in root.glob("*.json"):
            report = json.loads(path.read_text(encoding="utf-8"))
            for game in report.get("games", []):
                previous.add(tuple(sorted(game["opponent_deck"])))
    assert not quarantine & previous
