from __future__ import annotations

from scripts.annotate_tv_royale_type_repeatability import (
    annotate_type_repeatability,
)


def _row(checkpoint: str, *, safe: bool = True) -> dict[str, object]:
    return {
        "checkpoint": checkpoint,
        "improves_all_splits": True,
        "defensive_context_safe": safe,
        "mean_nll_improvement": 0.5,
    }


def test_requires_exact_safe_two_seed_group() -> None:
    summary = {
        "schema_version": 1,
        "candidates": [
            _row("alpha00625_seed1.pt"),
            _row("alpha00625_seed2.pt"),
            _row("alpha025_seed1.pt"),
            _row("alpha025_seed2.pt", safe=False),
            _row("endpoint.pt"),
        ],
    }
    metadata = {
        "alpha00625_seed1.pt": (0.0625, "slot", 1045901),
        "alpha00625_seed2.pt": (0.0625, "slot", 1045902),
        "alpha025_seed1.pt": (0.25, "slot", 1045901),
        "alpha025_seed2.pt": (0.25, "slot", 1045902),
    }

    result = annotate_type_repeatability(summary, metadata)

    assert result["schema_version"] == 2
    assert result["repeatable_group_count"] == 1
    assert result["repeatable_candidate_count"] == 2
    by_checkpoint = {row["checkpoint"]: row for row in result["candidates"]}
    assert by_checkpoint["alpha00625_seed1.pt"]["two_seed_repeatable"] is True
    assert by_checkpoint["alpha00625_seed2.pt"]["two_seed_repeatable"] is True
    assert by_checkpoint["alpha025_seed1.pt"]["two_seed_repeatable"] is False
    assert by_checkpoint["alpha025_seed2.pt"]["two_seed_repeatable"] is False
    assert by_checkpoint["endpoint.pt"]["two_seed_repeatable"] is False


def test_rejects_duplicate_seed_as_replication() -> None:
    summary = {
        "schema_version": 1,
        "candidates": [_row("a.pt"), _row("b.pt")],
    }
    metadata = {
        "a.pt": (0.0625, "play-gate", 1045901),
        "b.pt": (0.0625, "play-gate", 1045901),
    }

    result = annotate_type_repeatability(summary, metadata)

    assert result["repeatable_group_count"] == 0
    assert result["repeatable_candidate_count"] == 0
