from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.select_tv_royale_development_candidate import (
    load_development_screen_rows,
    select_development_candidate,
)


def _write_metrics(
    path: Path,
    *,
    checkpoint: Path,
    opponent: Path,
    decks: Path,
    seed: int,
    games: int = 12,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "checkpoint": str(checkpoint.resolve()),
                "opponent_mode": "policy",
                "opponent_checkpoint": str(opponent.resolve()),
                "sampling_decks_path": str(decks.resolve()),
                "seed": seed,
                "reward_profile": "defense-v2",
                "deterministic": True,
                "mirror_match": True,
                "metrics": {
                    "games": games,
                    "wins": 7,
                    "losses": 5,
                    "draws": games - 12,
                    "crown_diff_per_game": 0.25,
                },
            }
        )
    )


def test_prefers_proven_safe_strength_over_larger_development_margin() -> None:
    rows = [
        {"checkpoint": "safe.pt", "wins": 13, "losses": 11, "crown_difference": 4},
        {"checkpoint": "strong.pt", "wins": 18, "losses": 6, "crown_difference": 20},
    ]
    metadata = {
        "safe.pt": (0.0625, "slot"),
        "strong.pt": (0.25, "slot"),
    }

    selected = select_development_candidate(rows, metadata=metadata)

    assert selected is not None
    assert selected["checkpoint"] == "safe.pt"


def test_prefers_slot_decoder_at_same_strength() -> None:
    rows = [
        {"checkpoint": "play.pt", "wins": 14, "losses": 10, "crown_difference": 8},
        {"checkpoint": "slot.pt", "wins": 13, "losses": 11, "crown_difference": 4},
    ]
    metadata = {
        "play.pt": (0.0625, "play-gate"),
        "slot.pt": (0.0625, "slot"),
    }

    selected = select_development_candidate(rows, metadata=metadata)

    assert selected is not None
    assert selected["checkpoint"] == "slot.pt"


def test_returns_none_when_every_candidate_is_non_winning() -> None:
    rows = [
        {"checkpoint": "tie.pt", "wins": 12, "losses": 12, "crown_difference": 0},
        {"checkpoint": "loss.pt", "wins": 9, "losses": 15, "crown_difference": -10},
    ]

    assert select_development_candidate(rows, metadata={}) is None


def test_reopens_exact_paired_development_evidence(tmp_path: Path) -> None:
    candidate = tmp_path / "checkpoints" / "alpha00625.pt"
    candidate.parent.mkdir()
    candidate.touch()
    opponent = tmp_path / "parent.pt"
    opponent.touch()
    validation_decks = tmp_path / "validation.json"
    heldout_decks = tmp_path / "heldout.json"
    validation_decks.touch()
    heldout_decks.touch()
    screen_root = tmp_path / "screens"
    slug = f"{candidate.parent.name}_{candidate.stem}"
    _write_metrics(
        screen_root / slug / "validation12.metrics.json",
        checkpoint=candidate,
        opponent=opponent,
        decks=validation_decks,
        seed=1046501,
    )
    _write_metrics(
        screen_root / slug / "heldout12.metrics.json",
        checkpoint=candidate,
        opponent=opponent,
        decks=heldout_decks,
        seed=1046502,
    )

    rows = load_development_screen_rows(
        screen_root=screen_root,
        candidate_paths=[candidate],
        opponent_checkpoint=opponent,
        sampling_decks={
            "validation12": validation_decks,
            "heldout12": heldout_decks,
        },
        seeds={"validation12": 1046501, "heldout12": 1046502},
    )

    assert rows == [
        {
            "checkpoint": str(candidate.resolve()),
            "wins": 14,
            "losses": 10,
            "draws": 0,
            "crown_difference": 6.0,
        }
    ]


def test_rejects_stale_heldout_checkpoint_evidence(tmp_path: Path) -> None:
    candidate = tmp_path / "checkpoints" / "alpha00625.pt"
    stale = tmp_path / "checkpoints" / "stale.pt"
    candidate.parent.mkdir()
    candidate.touch()
    stale.touch()
    opponent = tmp_path / "parent.pt"
    opponent.touch()
    validation_decks = tmp_path / "validation.json"
    heldout_decks = tmp_path / "heldout.json"
    validation_decks.touch()
    heldout_decks.touch()
    screen_root = tmp_path / "screens"
    slug = f"{candidate.parent.name}_{candidate.stem}"
    _write_metrics(
        screen_root / slug / "validation12.metrics.json",
        checkpoint=candidate,
        opponent=opponent,
        decks=validation_decks,
        seed=1046501,
    )
    _write_metrics(
        screen_root / slug / "heldout12.metrics.json",
        checkpoint=stale,
        opponent=opponent,
        decks=heldout_decks,
        seed=1046502,
    )

    with pytest.raises(ValueError, match="development evidence mismatch"):
        load_development_screen_rows(
            screen_root=screen_root,
            candidate_paths=[candidate],
            opponent_checkpoint=opponent,
            sampling_decks={
                "validation12": validation_decks,
                "heldout12": heldout_decks,
            },
            seeds={"validation12": 1046501, "heldout12": 1046502},
        )
