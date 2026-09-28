from __future__ import annotations

from collections import defaultdict

import pytest

from scripts.balance_deck_pool_card_usage import balance_card_usage


def _payload() -> dict:
    return {
        "decks": [
            {
                "name": "a1",
                "archetype": "a",
                "cards": list("ABCDEFGH"),
                "sampling_weight": 0.8,
            },
            {
                "name": "a2",
                "archetype": "a",
                "cards": list("ABCDEFIJ"),
                "sampling_weight": 0.1,
            },
            {
                "name": "a3",
                "archetype": "a",
                "cards": list("ABCDKLMN"),
                "sampling_weight": 0.1,
            },
            {
                "name": "b1",
                "archetype": "b",
                "cards": list("OPQRSTUV"),
                "sampling_weight": 0.8,
            },
            {
                "name": "b2",
                "archetype": "b",
                "cards": list("OPQRSTWX"),
                "sampling_weight": 0.1,
            },
            {
                "name": "b3",
                "archetype": "b",
                "cards": ["O", "P", "Q", "R", "Y", "Z", "AA", "AB"],
                "sampling_weight": 0.1,
            },
        ]
    }


def test_card_balancing_preserves_decks_and_archetype_mass() -> None:
    source = _payload()
    output, report = balance_card_usage(
        source,
        iterations=500,
        learning_rate=0.05,
        weight_ratio_cap=4.0,
    )

    assert [row["cards"] for row in output["decks"]] == [
        row["cards"] for row in source["decks"]
    ]
    assert report["signature_changes"] == 0
    assert (
        report["after"]["maximum_to_minimum_ratio"]
        < report["before"]["maximum_to_minimum_ratio"]
    )
    assert report["weight_ratio_minimum"] >= 0.25 - 1e-12
    assert report["weight_ratio_maximum"] <= 4.0 + 1e-12
    masses: dict[str, float] = defaultdict(float)
    for row in output["decks"]:
        masses[row["archetype"]] += row["sampling_weight"]
    assert masses == pytest.approx({"a": 0.5, "b": 0.5})


@pytest.mark.parametrize(
    ("iterations", "learning_rate", "cap"),
    ((0, 0.03, 4.0), (10, 0.0, 4.0), (10, 0.03, 1.0)),
)
def test_card_balancing_rejects_invalid_controls(
    iterations: int,
    learning_rate: float,
    cap: float,
) -> None:
    with pytest.raises(ValueError):
        balance_card_usage(
            _payload(),
            iterations=iterations,
            learning_rate=learning_rate,
            weight_ratio_cap=cap,
        )
