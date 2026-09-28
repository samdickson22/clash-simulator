from __future__ import annotations

from scripts.exclude_deck_pool_signatures import exclude_deck_signatures


def _deck(name: str, archetype: str, suffix: str, weight: float) -> dict[str, object]:
    return {
        "name": name,
        "archetype": archetype,
        "cards": [f"card-{index}" for index in range(7)] + [suffix],
        "sampling_weight": weight,
    }


def test_exact_signature_exclusion_preserves_archetype_weight() -> None:
    excluded = _deck("held out", "cycle", "held", 0.25)
    source = {
        "schema_version": 1,
        "decks": [
            excluded,
            _deck("retained cycle", "cycle", "kept", 0.75),
            _deck("retained beatdown", "beatdown", "beat", 1.0),
        ],
    }

    output, manifest = exclude_deck_signatures(
        source,
        [{"decks": [{**excluded, "cards": list(reversed(excluded["cards"]))}]}],
    )

    assert [row["name"] for row in output["decks"]] == [
        "retained cycle",
        "retained beatdown",
    ]
    assert output["decks"][0]["sampling_weight"] == 1.0
    assert output["decks"][1]["sampling_weight"] == 1.0
    assert manifest["retained_exclusion_overlap"] == 0
    assert manifest["archetype_weight_before"] == manifest["archetype_weight_after"]
