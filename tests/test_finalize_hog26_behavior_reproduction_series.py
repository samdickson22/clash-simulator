from __future__ import annotations

import pytest

from scripts.finalize_hog26_behavior_reproduction_series import aggregate


def _comparison(seed: int, *, matches: int = 28, behavior: bool = True) -> dict:
    return {
        "base_seed": seed,
        "games": 28,
        "teacher_checkpoint_sha256": "a" * 64,
        "student_checkpoint_sha256": "b" * 64,
        "teacher_score": 2,
        "student_score": 2,
        "exact_action_hash_rows": 28,
        "exact_action_hash_matches": matches,
        "behavior_gate_pass": behavior,
    }


def test_series_requires_two_exact_action_hashed_28_game_seeds() -> None:
    result = aggregate([_comparison(1), _comparison(2)])
    assert result["games_per_arm"] == 56
    assert result["exact_action_hash_match_rate"] == 1.0
    assert result["status"] == "passed-closed-loop"


@pytest.mark.parametrize(
    "comparisons",
    (
        [_comparison(1), _comparison(2, matches=27)],
        [_comparison(1), _comparison(2, behavior=False)],
    ),
)
def test_series_rejects_any_hash_or_behavior_failure(comparisons: list[dict]) -> None:
    assert aggregate(comparisons)["status"] == "rejected"


def test_series_rejects_reused_seed() -> None:
    with pytest.raises(ValueError, match="unique"):
        aggregate([_comparison(1), _comparison(1)])
