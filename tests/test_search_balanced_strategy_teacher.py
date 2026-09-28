from __future__ import annotations

import math
from dataclasses import asdict

from clasher.rl.strategy_bots import BalancedStrategyConfig
from scripts.search_balanced_strategy_teacher import candidate_config


def test_default_candidate_preserves_production_balanced_weights() -> None:
    assert candidate_config(0, 1075201) == BalancedStrategyConfig()


def test_search_candidates_are_deterministic_and_bounded() -> None:
    first = candidate_config(7, 1075201)
    repeated = candidate_config(7, 1075201)
    other = candidate_config(8, 1075201)
    assert first == repeated
    assert first != other
    assert all(math.isfinite(value) for value in asdict(first).values())
    assert 0.0 <= first.noop_elixir_threshold <= 10.0
    assert first.threat_scale > 0.0
    assert first.offense_y_scale > 0.0


def test_search_candidate_rejects_negative_index() -> None:
    try:
        candidate_config(-1, 1075201)
    except ValueError as error:
        assert "non-negative" in str(error)
    else:
        raise AssertionError("negative search candidate index should fail")
