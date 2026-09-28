from __future__ import annotations

from typing import Any

from scripts.select_tv_royale_location_candidates import (
    SPLITS,
    summarize_location_candidates,
)


def _results(
    checkpoints: dict[str, tuple[float, float]],
) -> dict[str, dict[str, dict[str, float]]]:
    return {
        split: {
            checkpoint: {
                "conditional_location_nll": location_nll,
                "action_type_nll": type_nll,
            }
            for checkpoint, (location_nll, type_nll) in checkpoints.items()
        }
        for split in SPLITS
    }


def test_selects_repeatable_epoch_direction_with_best_heldout_gain() -> None:
    parent = "/tmp/parent.pt"
    candidates = {
        "/tmp/e5s1.pt": (5, 1046001),
        "/tmp/e5s2.pt": (5, 1046002),
        "/tmp/e20s1.pt": (20, 1046001),
        "/tmp/e20s2.pt": (20, 1046002),
    }
    mapping: dict[str, dict[str, Any]] = {
        parent: {"parent": parent, "training_epochs": 0, "training_seed": 0},
        **{
            checkpoint: {
                "parent": parent,
                "training_epochs": epochs,
                "training_seed": seed,
            }
            for checkpoint, (epochs, seed) in candidates.items()
        },
    }
    results = _results(
        {
            parent: (10.0, 2.0),
            "/tmp/e5s1.pt": (4.0, 2.0),
            "/tmp/e5s2.pt": (4.1, 2.0),
            "/tmp/e20s1.pt": (4.5, 2.0),
            "/tmp/e20s2.pt": (4.6, 2.0),
        }
    )
    metadata = {checkpoint: (0.0625, "slot") for checkpoint in candidates}

    summary = summarize_location_candidates(mapping, results, metadata)

    assert summary["repeatable_group_count"] == 2
    assert summary["eligible_count"] == 4
    assert summary["gameplay_candidates"] == [
        "/tmp/e5s1.pt",
        "/tmp/e5s2.pt",
    ]


def test_rejects_single_seed_and_nonpreserving_type_changes() -> None:
    parent = "/tmp/parent.pt"
    mapping = {
        parent: {"parent": parent, "training_epochs": 0, "training_seed": 0},
        "/tmp/only-one-seed.pt": {
            "parent": parent,
            "training_epochs": 5,
            "training_seed": 1046001,
        },
        "/tmp/type-drift-s1.pt": {
            "parent": parent,
            "training_epochs": 20,
            "training_seed": 1046001,
        },
        "/tmp/type-drift-s2.pt": {
            "parent": parent,
            "training_epochs": 20,
            "training_seed": 1046002,
        },
    }
    results = _results(
        {
            parent: (10.0, 2.0),
            "/tmp/only-one-seed.pt": (4.0, 2.0),
            "/tmp/type-drift-s1.pt": (4.0, 1.9),
            "/tmp/type-drift-s2.pt": (4.0, 1.9),
        }
    )
    metadata = {
        checkpoint: (0.0625, "slot")
        for checkpoint in mapping
        if checkpoint != parent
    }

    summary = summarize_location_candidates(mapping, results, metadata)

    assert summary["repeatable_group_count"] == 0
    assert summary["eligible_count"] == 0
    assert summary["gameplay_candidates"] == []
