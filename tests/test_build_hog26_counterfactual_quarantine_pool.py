from __future__ import annotations

import json
from pathlib import Path

from scripts.build_hog26_counterfactual_quarantine_pool import build_pool


def _deck(archetype: str, suffix: str) -> dict[str, object]:
    return {
        "name": f"{archetype}-{suffix}",
        "archetype": archetype,
        "cards": [f"{archetype}-{suffix}-{index}" for index in range(8)],
    }


def test_quarantine_pool_excludes_gameplay_and_balances_archetypes(
    tmp_path: Path,
) -> None:
    rows = [_deck(archetype, suffix) for archetype in ("a", "b") for suffix in ("0", "1")]
    pool = tmp_path / "pool.json"
    pool.write_text(json.dumps({"decks": rows}), encoding="utf-8")
    gameplay = tmp_path / "gameplay"
    gameplay.mkdir()
    gameplay.joinpath("balanced.json").write_text(
        json.dumps(
            {
                "games": [
                    {
                        "opponent_deck": rows[0]["cards"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = build_pool(source_pools=[pool], gameplay_roots=[gameplay])

    assert result["deck_count"] == 3
    assert result["excluded_gameplay_decks"] == 1
    assert result["exact_overlap_with_gameplay"] == 0
    assert result["archetype_deck_counts"] == {"a": 1, "b": 2}
    assert result["archetype_weight_sums"] == {"a": 0.5, "b": 0.5}
