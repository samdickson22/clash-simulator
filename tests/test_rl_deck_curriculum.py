from __future__ import annotations

from collections import defaultdict

from clasher.rl.card_semantics import semantic_card_profile
from clasher.rl.deck_curriculum import (
    CurriculumDeck,
    _is_valid_deck,
    generate_structured_decks,
    infer_archetype,
    split_curriculum,
)
from clasher.rl.deck_pool import load_deck_pool


def _seed_decks() -> list[CurriculumDeck]:
    return [
        CurriculumDeck(
            name="Hog seed",
            cards=(
                "HogRider",
                "Musketeer",
                "Cannon",
                "Fireball",
                "Zap",
                "Skeletons",
                "IceGolem",
                "IceSpirit",
            ),
            archetype="hog",
            source="test",
        ),
        CurriculumDeck(
            name="X-Bow seed",
            cards=(
                "Xbow",
                "Tesla",
                "Archers",
                "Fireball",
                "Log",
                "Skeletons",
                "IceGolem",
                "IceSpirit",
            ),
            archetype="x-bow",
            source="test",
        ),
    ]


def test_structured_deck_generation_is_deterministic_and_valid() -> None:
    card_pool = sorted({card for deck in load_deck_pool("decks.json") for card in deck})
    first = generate_structured_decks(
        _seed_decks(),
        card_pool=card_pool,
        variants_per_seed=4,
        seed=1040001,
    )
    second = generate_structured_decks(
        _seed_decks(),
        card_pool=card_pool,
        variants_per_seed=4,
        seed=1040001,
    )

    assert first == second
    assert len(first) == 10
    profiles = {name: semantic_card_profile(name) for name in card_pool}
    assert all(_is_valid_deck(deck.cards, profiles) for deck in first)
    assert all(infer_archetype(deck.cards) == deck.archetype for deck in first)
    assert len({tuple(sorted(deck.cards)) for deck in first}) == len(first)


def test_split_holds_out_entire_archetypes_without_deck_overlap() -> None:
    decks = _seed_decks() + [
        CurriculumDeck(
            name=f"Hog duplicate {index}",
            cards=tuple(_seed_decks()[0].cards[:-1]) + (replacement,),
            archetype="hog",
            source="test",
        )
        for index, replacement in enumerate(("FireSpirit", "ElectroSpirit"), start=1)
    ]
    train, validation, heldout = split_curriculum(
        decks,
        validation_fraction=0.25,
        seed=17,
        held_out_archetypes=frozenset({"x-bow"}),
    )

    assert {deck.archetype for deck in heldout} == {"x-bow"}
    assert not ({deck.archetype for deck in heldout} & {deck.archetype for deck in train + validation})
    keys = [
        {tuple(sorted(deck.cards)) for deck in split}
        for split in (train, validation, heldout)
    ]
    assert keys[0].isdisjoint(keys[1])
    assert keys[0].isdisjoint(keys[2])
    assert keys[1].isdisjoint(keys[2])


def test_infer_archetype_uses_specific_win_condition_priority() -> None:
    assert infer_archetype(("Xbow", "HogRider")) == "x-bow"
    assert infer_archetype(("GoblinBarrel", "Miner")) == "log-bait"


def test_generated_pool_weights_balance_archetypes() -> None:
    pool = load_deck_pool("datasets/deck_curriculum_v2_seed1040001/train.json")
    assert len(pool) == 455

    # Each archetype's individual deck weight is 1 / number of decks in that
    # archetype, so total sampling mass is equal despite unequal deck counts.
    import json
    from pathlib import Path

    payload = json.loads(
        Path("datasets/deck_curriculum_v2_seed1040001/train.json").read_text()
    )
    totals: dict[str, float] = defaultdict(float)
    for deck in payload["decks"]:
        totals[deck["archetype"]] += deck["sampling_weight"]
    assert len(totals) >= 8
    assert all(abs(total - 1.0) < 1e-9 for total in totals.values())
