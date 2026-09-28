from __future__ import annotations

from clasher.rl.value_guided_search import CandidateValue
from scripts.collect_terminal_counterfactual_corpus import (
    _best_terminal_candidate,
)


def test_terminal_best_action_uses_outcome_crowns_then_damage() -> None:
    candidates = (
        CandidateValue(10, 1.0, crown_difference=0, tower_damage_difference=50.0),
        CandidateValue(11, 1.0, crown_difference=1, tower_damage_difference=0.0),
        CandidateValue(12, 1.0, crown_difference=1, tower_damage_difference=25.0),
        CandidateValue(13, 0.5, crown_difference=3, tower_damage_difference=900.0),
    )

    assert _best_terminal_candidate(candidates).action == 12


def test_terminal_best_action_preserves_base_on_exact_tie() -> None:
    candidates = (
        CandidateValue(20, 0.5, crown_difference=0, tower_damage_difference=0.0),
        CandidateValue(10, 0.5, crown_difference=0, tower_damage_difference=0.0),
    )

    assert _best_terminal_candidate(candidates).action == 20
