from __future__ import annotations

import pytest

from scripts.audit_counterfactual_deck_membership import audit_membership

LEARNER = tuple(sorted(f"L{index}" for index in range(8)))
OPPONENT = tuple(sorted(f"O{index}" for index in range(8)))
FORBIDDEN = tuple(sorted(f"F{index}" for index in range(8)))


def _report(opponent: tuple[str, ...] = OPPONENT) -> dict[str, object]:
    return {
        "games": [
            {
                "controlled_player": 0,
                "decks": [list(LEARNER), list(opponent)],
            },
            {
                "controlled_player": 1,
                "decks": [list(opponent), list(LEARNER)],
            },
        ]
    }


def test_membership_audit_accepts_authorized_decks_and_both_seats() -> None:
    result = audit_membership(
        _report(),
        learner_pool={LEARNER: "hog"},
        opponent_pool={OPPONENT: "giant"},
        forbidden_opponent_pool={FORBIDDEN},
        expected_games=2,
    )
    assert result["passed"] is True
    assert result["sampled_opponent_decks"] == 1
    assert result["candidate_seats"] == {"0": 1, "1": 1}


def test_membership_audit_rejects_unknown_or_overlapping_opponents() -> None:
    with pytest.raises(ValueError, match="outside opponent authority"):
        audit_membership(
            _report(FORBIDDEN),
            learner_pool={LEARNER: "hog"},
            opponent_pool={OPPONENT: "giant"},
            forbidden_opponent_pool=set(),
            expected_games=2,
        )
    with pytest.raises(ValueError, match="pools overlap"):
        audit_membership(
            _report(),
            learner_pool={LEARNER: "hog"},
            opponent_pool={OPPONENT: "giant"},
            forbidden_opponent_pool={OPPONENT},
            expected_games=2,
        )
