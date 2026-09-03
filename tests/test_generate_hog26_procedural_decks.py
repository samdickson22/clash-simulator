from __future__ import annotations

from collections import Counter
from pathlib import Path

from scripts.generate_hog26_procedural_decks import generate

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "training_decks"
    / "simple_gym_supported_v1.json"
)


def test_procedural_deck_families_are_deterministic_and_split_safe() -> None:
    arguments = {
        "seed": 1278401,
        "train_families": 8,
        "development_families": 4,
        "holdout_families": 4,
        "variants_per_family": 4,
        "learner_deck_name": "Hog 2.6 Cycle",
        "reserved_decks": ("RHogs AQ 2.9 Cycle",),
    }
    first = generate(SOURCE, **arguments)
    second = generate(SOURCE, **arguments)
    assert first == second
    assert first["counts"]["decks"] == 65
    assert first["counts"]["opponent_decks"] == 64
    assert Counter(row["split"] for row in first["decks"]) == {
        "learner": 1,
        "train": 32,
        "development": 16,
        "holdout": 16,
    }
    family_splits: dict[str, set[str]] = {}
    family_cards: dict[str, set[str]] = {}
    family_parents: dict[str, tuple[str, ...]] = {}
    source_decks = {
        tuple(sorted(row["cards"]))
        for row in __import__("json").loads(SOURCE.read_text())["decks"]
    }
    source_by_name = {
        row["name"]: set(row["cards"])
        for row in __import__("json").loads(SOURCE.read_text())["decks"]
    }
    generated = set()
    for row in first["decks"]:
        if row["split"] == "learner":
            assert row["name"] == "Hog 2.6 Cycle"
            assert row["role"] == "fixed-policy-deck"
            continue
        cards = tuple(sorted(row["cards"]))
        assert len(cards) == len(set(cards)) == 8
        assert cards not in source_decks
        assert cards not in generated
        generated.add(cards)
        family_splits.setdefault(row["family_id"], set()).add(row["split"])
        family_cards.setdefault(row["family_id"], set()).update(row["cards"])
        family_parents.setdefault(
            row["family_id"], tuple(row["parent_decks"])
        )
        assert "RHogs AQ 2.9 Cycle" not in row["parent_decks"]
    assert all(len(splits) == 1 for splits in family_splits.values())
    assert Counter(
        parent for parents in family_parents.values() for parent in parents
    ) == Counter(
        name for name in source_by_name if name != "RHogs AQ 2.9 Cycle"
    )
    for family_id, parents in family_parents.items():
        assert family_cards[family_id] == set().union(
            *(source_by_name[parent] for parent in parents)
        )
    eligible_cards = set().union(
        *(
            cards
            for name, cards in source_by_name.items()
            if name != "RHogs AQ 2.9 Cycle"
        )
    )
    train_cards = {
        card
        for row in first["decks"]
        if row["split"] == "train"
        for card in row["cards"]
    }
    assert train_cards == eligible_cards
