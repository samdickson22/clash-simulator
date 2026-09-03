from __future__ import annotations

import pytest

from scripts.evaluate_hog26_outcome_counterfactual_pairs import (
    compare_pair,
    root_phase,
)


def test_root_phase_uses_predeclared_thirds_and_rejects_invalid_progress() -> None:
    assert root_phase(0.0) == "early"
    assert root_phase(1 / 3) == "middle"
    assert root_phase(2 / 3) == "late"
    assert root_phase(1.0) == "late"
    with pytest.raises(ValueError, match="progress"):
        root_phase(1.01)


def _probe(*, terminal: bool) -> dict[str, object]:
    rows = []
    for action, short_score, final_outcome, final_margin in (
        (10, -0.2, -1, -0.4),
        (20, 0.3, 1, 0.2),
        (30, 0.1, 1, 0.1),
    ):
        rows.append(
            {
                "action": action,
                "terminal": terminal,
                "terminal_outcome": final_outcome if terminal else 0,
                "terminal_tower_margin": final_margin if terminal else None,
                "actor_visible_branch_utility": (
                    float(final_outcome) if terminal else short_score
                ),
                "outcome_bootstrap_margin": None if terminal else final_margin,
                "outcome_ensemble_disagreement": None if terminal else 0.01,
            }
        )
    return {
        "schema": "clasher.simple-counterfactual-teacher-probe.v4",
        "checkpoint_sha256": "a" * 64,
        "seed": 1,
        "warmup_steps": 10,
        "root_progress": 0.2,
        "opponent_strategy": "balanced",
        "opponent_deck": "Giant",
        "learner_seat": 0,
        "candidate_selector": "hand-slot-spatial-stratified-v1",
        "stop_when_all_terminal": terminal,
        "rows": rows,
    }


def test_compare_pair_uses_outcome_before_margin() -> None:
    result = compare_pair(_probe(terminal=False), _probe(terminal=True), margin_threshold=0.02)  # type: ignore[arg-type]
    outcome = result["variants"]["outcome"]
    assert outcome["selected_action"] == 20
    assert outcome["reference_best_action"] == 20
    assert outcome["worse_terminal_outcome"] is False
    assert outcome["same_outcome_margin_regret"] == 0.0
    assert outcome["pairwise_concordance"] == 1.0
