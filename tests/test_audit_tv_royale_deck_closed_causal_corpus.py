from __future__ import annotations

from scripts.audit_tv_royale_deck_closed_causal_corpus import (
    MINIMUM_ACTION_TARGETS,
    MINIMUM_FULL_ACTOR_TARGETS,
    MINIMUM_REPLAY_GROUPS,
)


def test_fresh_causal_bc_thresholds_require_a_real_replay_corpus() -> None:
    assert MINIMUM_REPLAY_GROUPS >= 20
    assert MINIMUM_ACTION_TARGETS >= 1_000
    assert MINIMUM_FULL_ACTOR_TARGETS >= 250
