from __future__ import annotations

from scripts.select_fresh_f3_hazard_repair_anchor import CANDIDATES


def test_repair_anchor_candidate_set_is_the_predeclared_checkpoint_subset() -> None:
    assert CANDIDATES == (23, 24, 29, 30)
