from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.finalize_fresh_f3_hazard_parentheavy_random_confirmation import finalize


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_confirmation_selects_plain_when_combined_random_is_within_one(tmp_path: Path) -> None:
    initial = tmp_path / "initial.json"
    _write(
        initial,
        {
            "selected": "anchor",
            "random_confirmation_authorized": True,
            "arms": {
                "anchor": {
                    "checkpoint_sha256": "anchor-sha",
                    "random": {"wins": 15, "losses": 9},
                },
                "plain": {
                    "checkpoint_sha256": "plain-sha",
                    "random": {"wins": 12, "losses": 12},
                    "rejection_reasons": ["random_regression"],
                },
            },
        },
    )
    root = tmp_path / "confirmation"
    for arm, wins, losses, crowns in (
        ("anchor", 15, 9, 12),
        ("plain", 12, 12, 11),
    ):
        _write(
            initial.parent / arm / "random24.metrics.json",
            {
                "metrics": {
                    "games": 24,
                    "wins": wins,
                    "losses": losses,
                    "crown_diff_per_game": crowns / 24,
                    "candidate_noop_when_playable": 0.94,
                }
            },
        )
    for arm, sha, wins, losses, crowns, noop in (
        ("anchor", "anchor-sha", 31, 17, 32, 0.947),
        ("plain", "plain-sha", 33, 15, 43, 0.943),
    ):
        _write(
            root / f"{arm}.metrics.json",
            {
                "checkpoint_sha256": sha,
                "seed": 1_070_101,
                "opponent_mode": "random",
                "mirror_match": True,
                "sampling_decks_sha256": "pool-sha",
                "metrics": {
                    "games": 48,
                    "wins": wins,
                    "losses": losses,
                    "crown_diff_per_game": crowns / 48,
                    "candidate_noop_when_playable": noop,
                },
            },
        )

    result = finalize(
        initial_decision_path=initial,
        confirmation_root=root,
        output=tmp_path / "decision.json",
    )

    assert result["selected"] == "plain"
    assert result["combined_random"]["anchor"]["wins"] == 46
    assert result["combined_random"]["plain"]["wins"] == 45
    assert result["combined_random"]["plain"]["crown_difference"] == 54
    assert result["plain_rejection_reasons"] == []
    assert result["hog_specialist_curriculum_authorized"] is True
    assert result["promotion_authorized"] is False
    assert result["evidence_sha256"][str(initial.resolve())] == hashlib.sha256(
        initial.read_bytes()
    ).hexdigest()
