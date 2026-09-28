from __future__ import annotations

from scripts.build_card_complete_deck_splits import (
    build_card_complete_splits,
    signature,
)


def _deck(index: int, archetype: str, rare: str | None = None) -> dict[str, object]:
    cards = [f"C{archetype}-{(index + slot) % 10}" for slot in range(8)]
    if rare is not None:
        cards[-1] = rare
    return {
        "name": f"{archetype}-{index}",
        "archetype": archetype,
        "cards": cards,
    }


def test_card_complete_split_repairs_rare_card_and_preserves_disjointness() -> None:
    payload = {
        "decks": [
            *[_deck(index, "a", "Rare" if index == 0 else None) for index in range(8)],
            *[_deck(index, "b") for index in range(8)],
        ]
    }

    splits, report = build_card_complete_splits(
        payload,
        validation_fraction=0.25,
        heldout_fraction=0.25,
        seed=11,
    )

    train_cards = {card for row in splits["train"] for card in signature(row)}
    all_cards = {card for row in payload["decks"] for card in signature(row)}
    assert train_cards == all_cards
    assert report["training_card_coverage_rate"] == 1.0
    assert report["exact_signature_overlaps"] == {
        "train_validation": 0,
        "train_heldout": 0,
        "validation_heldout": 0,
    }
    for archetype in ("a", "b"):
        assert any(row["archetype"] == archetype for row in splits["train"])
        assert any(row["archetype"] == archetype for row in splits["heldout"])


def test_card_complete_split_is_deterministic() -> None:
    payload = {
        "decks": [
            *[_deck(index, "a") for index in range(8)],
            *[_deck(index, "b") for index in range(8)],
        ]
    }

    first, first_report = build_card_complete_splits(
        payload,
        validation_fraction=0.2,
        heldout_fraction=0.2,
        seed=17,
    )
    second, second_report = build_card_complete_splits(
        payload,
        validation_fraction=0.2,
        heldout_fraction=0.2,
        seed=17,
    )

    assert first == second
    assert first_report == second_report
