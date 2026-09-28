from pathlib import Path

import pytest

from clasher.rl.human_meta_decks import select_recurring_human_meta_decks
from clasher.rl.replay_split import ReplaySplitRecord


def _record(
    replay: str,
    signature: tuple[str, ...],
    *,
    archetype: str = "hog",
) -> ReplaySplitRecord:
    cards = tuple(
        item.removeprefix("enabled:")
        for item in signature
        if item.startswith("enabled:")
    )
    return ReplaySplitRecord(
        replay=replay,
        arena="arena_20",
        arena_number=20,
        corpus=Path(f"{replay}.npz"),
        deck_signature=signature,
        enabled_cards=cards,
        archetype=archetype,
        samples=10,
        plays=7,
        noops=3,
    )


def test_selects_repeated_exact_fully_enabled_deck() -> None:
    signature = tuple(f"enabled:Card{index}" for index in range(8))
    decks, rejected = select_recurring_human_meta_decks(
        (_record("a", signature), _record("b", signature))
    )

    assert len(decks) == 1
    assert decks[0].cards == tuple(f"Card{index}" for index in range(8))
    assert decks[0].occurrences == 2
    assert decks[0].samples == 20
    assert rejected == {}


def test_partial_observation_can_join_repeated_complete_deck() -> None:
    signature = tuple(f"enabled:Card{index}" for index in range(8))
    decks, _ = select_recurring_human_meta_decks(
        (_record("partial", signature[:-1]), _record("complete", signature))
    )

    assert len(decks) == 1
    assert decks[0].cards == tuple(f"Card{index}" for index in range(8))
    assert decks[0].occurrences == 2


def test_rejects_singletons_overcomplete_and_unmapped_components() -> None:
    singleton = tuple(f"enabled:Single{index}" for index in range(8))
    overcomplete = tuple(f"enabled:Over{index}" for index in range(9))
    unmapped = tuple(f"enabled:Raw{index}" for index in range(7)) + (
        "raw:futurecard",
    )
    records = (
        _record("singleton", singleton),
        _record("over-a", overcomplete),
        _record("over-b", overcomplete),
        _record("raw-a", unmapped),
        _record("raw-b", unmapped),
    )

    decks, rejected = select_recurring_human_meta_decks(records)

    assert decks == ()
    assert rejected == {
        "contains_unmapped_card": 1,
        "not_exactly_eight_signature_items": 1,
        "too_few_replays": 1,
    }


def test_minimum_recurrence_cannot_be_disabled() -> None:
    with pytest.raises(ValueError, match="at least two"):
        select_recurring_human_meta_decks((), min_replays=1)
