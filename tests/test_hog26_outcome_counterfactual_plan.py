from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

PLAN = (
    Path(__file__).resolve().parents[1]
    / "reports"
    / "hog26_outcome_counterfactual_plan_seed1279001.json"
)


def test_counterfactual_plan_is_balanced_and_predeclared() -> None:
    payload = json.loads(PLAN.read_text())
    assert payload["schema"] == "clasher.hog26.outcome-counterfactual-plan.v1"
    assert payload["status"] == "predeclared-before-natural-holdout-publication"
    assert payload["required_outcome_model_seeds"] == [1277501, 1278101, 1278102]
    assert payload["mutation_authorized"] is False

    roots = payload["roots"]
    assert len(roots) == 12
    assert len({row["id"] for row in roots}) == 12
    assert len({row["seed"] for row in roots}) == 12
    assert Counter(row["phase"] for row in roots) == {
        "early": 4,
        "middle": 4,
        "late": 4,
    }
    assert Counter(row["learner_seat"] for row in roots) == {0: 6, 1: 6}
    assert set(Counter(row["opponent_strategy"] for row in roots).values()) == {4}
    assert set(Counter(row["opponent_deck"] for row in roots).values()) == {3}

    thirds = {"early": (0.0, 1 / 3), "middle": (1 / 3, 2 / 3), "late": (2 / 3, 1.0)}
    for row in roots:
        lower, upper = row["progress"]
        phase_lower, phase_upper = thirds[row["phase"]]
        assert phase_lower <= lower < upper <= phase_upper
        assert row["warmup_steps"] > 0
        assert row["root_search_steps"] > 0

    assert payload["aggregate_gates"] == {
        "minimum_roots": 12,
        "minimum_roots_per_phase": 2,
        "minimum_roots_per_seat": 3,
        "minimum_opponent_strategies": 3,
        "minimum_roots_per_opponent": 2,
        "maximum_worse_terminal_outcomes": 0,
        "minimum_pairwise_concordance": 0.65,
        "maximum_mean_same_outcome_margin_regret": 0.1,
    }
