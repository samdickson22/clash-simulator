from __future__ import annotations

from scripts.select_tv_royale_gameplay_candidates import select_gameplay_candidates


def _row(checkpoint: str, improvement: float, *, safe: bool = True) -> dict[str, object]:
    return {
        "checkpoint": checkpoint,
        "improves_all_splits": True,
        "defensive_context_safe": safe,
        "two_seed_repeatable": True,
        "mean_nll_improvement": improvement,
    }


def test_selects_weak_middle_and_strong_candidates_per_hierarchy() -> None:
    rows = [
        _row("seed1/alpha003125_slot.pt", 0.1),
        _row("seed2/alpha003125_slot.pt", 0.2),
        _row("seed1/alpha050_slot.pt", 0.5),
        _row("seed2/alpha050_slot.pt", 0.45),
        _row("seed1/alpha075_slot.pt", 0.9),
        _row("seed2/alpha075_slot.pt", 0.85),
        _row("seed1/alpha003125_playgate.pt", 0.1),
        _row("seed2/alpha003125_playgate.pt", 0.09),
        _row("seed1/alpha050_playgate.pt", 0.4),
        _row("seed2/alpha050_playgate.pt", 0.39),
        _row("seed1/alpha075_playgate.pt", 0.8),
        _row("seed2/alpha075_playgate.pt", 0.79),
    ]
    metadata = {
        "seed1/alpha003125_slot.pt": (0.03125, "slot"),
        "seed2/alpha003125_slot.pt": (0.03125, "slot"),
        "seed1/alpha050_slot.pt": (0.50, "slot"),
        "seed2/alpha050_slot.pt": (0.50, "slot"),
        "seed1/alpha075_slot.pt": (0.75, "slot"),
        "seed2/alpha075_slot.pt": (0.75, "slot"),
        "seed1/alpha003125_playgate.pt": (0.03125, "play-gate"),
        "seed2/alpha003125_playgate.pt": (0.03125, "play-gate"),
        "seed1/alpha050_playgate.pt": (0.50, "play-gate"),
        "seed2/alpha050_playgate.pt": (0.50, "play-gate"),
        "seed1/alpha075_playgate.pt": (0.75, "play-gate"),
        "seed2/alpha075_playgate.pt": (0.75, "play-gate"),
    }

    assert select_gameplay_candidates(rows, metadata=metadata) == [
        "seed2/alpha003125_slot.pt",
        "seed1/alpha003125_slot.pt",
        "seed1/alpha050_slot.pt",
        "seed2/alpha050_slot.pt",
        "seed1/alpha075_slot.pt",
        "seed2/alpha075_slot.pt",
        "seed1/alpha003125_playgate.pt",
        "seed2/alpha003125_playgate.pt",
        "seed1/alpha050_playgate.pt",
        "seed2/alpha050_playgate.pt",
        "seed1/alpha075_playgate.pt",
        "seed2/alpha075_playgate.pt",
    ]


def test_rejects_offline_or_defensive_failures() -> None:
    rows = [
        _row("seed/alpha025_slot.pt", 0.5, safe=False),
        {
            **_row("seed/alpha050_slot.pt", 0.7),
            "improves_all_splits": False,
        },
    ]

    assert select_gameplay_candidates(rows, metadata={}) == []


def test_rejects_nonrepeatable_two_seed_candidate() -> None:
    rows = [
        {
            **_row("seed/alpha00625_slot.pt", 0.5),
            "two_seed_repeatable": False,
        }
    ]

    assert select_gameplay_candidates(rows, metadata={}) == []


def test_rejects_candidate_without_two_seed_evidence() -> None:
    row = _row("seed/alpha00625_slot.pt", 0.5)
    del row["two_seed_repeatable"]

    assert select_gameplay_candidates([row], metadata={}) == []


def test_safe_probe_targets_six_and_a_quarter_percent_not_weakest() -> None:
    rows = [
        _row("seed/alpha000390625_slot.pt", 0.01),
        _row("seed/alpha00625_slot.pt", 0.2),
        _row("seed/alpha050_slot.pt", 0.5),
        _row("seed/alpha075_slot.pt", 0.9),
    ]
    metadata = {
        "seed/alpha000390625_slot.pt": (0.00390625, "slot"),
        "seed/alpha00625_slot.pt": (0.0625, "slot"),
        "seed/alpha050_slot.pt": (0.50, "slot"),
        "seed/alpha075_slot.pt": (0.75, "slot"),
    }

    assert select_gameplay_candidates(rows, metadata=metadata) == [
        "seed/alpha00625_slot.pt",
        "seed/alpha050_slot.pt",
        "seed/alpha075_slot.pt",
    ]
