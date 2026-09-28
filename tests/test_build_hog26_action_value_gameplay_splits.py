from __future__ import annotations

from scripts.build_hog26_action_value_gameplay_splits import (
    _signature,
    split_decks,
)


def test_action_value_gameplay_splits_are_stratified_and_disjoint() -> None:
    decks = []
    for archetype in ("x-bow", "graveyard"):
        for index in range(6):
            decks.append(
                {
                    "name": f"{archetype}-{index}",
                    "archetype": archetype,
                    "cards": [archetype, f"card-{index}"],
                    "sampling_weight": 1.0,
                }
            )
    source = {
        "schema_version": 1,
        "metadata": {"split": "heldout"},
        "decks": decks,
    }

    screen, quarantine = split_decks(source)

    assert len(screen["decks"]) == 4
    assert len(quarantine["decks"]) == 8
    assert {row["archetype"] for row in screen["decks"]} == {
        "x-bow",
        "graveyard",
    }
    assert {row["archetype"] for row in quarantine["decks"]} == {
        "x-bow",
        "graveyard",
    }
    assert not (
        {_signature(row) for row in screen["decks"]}
        & {_signature(row) for row in quarantine["decks"]}
    )
    assert sum(row["sampling_weight"] for row in screen["decks"]) == 1.0
    assert sum(row["sampling_weight"] for row in quarantine["decks"]) == 1.0


def test_action_value_gameplay_splits_exclude_tuning_decks() -> None:
    decks = []
    for archetype in ("x-bow", "graveyard"):
        for index in range(7):
            decks.append(
                {
                    "name": f"{archetype}-{index}",
                    "archetype": archetype,
                    "cards": [archetype, f"card-{index}"],
                    "sampling_weight": 1.0,
                }
            )
    source = {
        "schema_version": 1,
        "metadata": {"split": "heldout"},
        "decks": decks,
    }
    excluded = frozenset({_signature(decks[0]), _signature(decks[-1])})

    screen, quarantine = split_decks(
        source,
        excluded_signatures=excluded,
    )

    retained = {
        _signature(row) for row in (*screen["decks"], *quarantine["decks"])
    }
    assert retained.isdisjoint(excluded)
    assert len(retained) == len(decks) - len(excluded)
    assert {row["archetype"] for row in screen["decks"]} == {
        "x-bow",
        "graveyard",
    }
    assert {row["archetype"] for row in quarantine["decks"]} == {
        "x-bow",
        "graveyard",
    }
