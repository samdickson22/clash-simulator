"""Verify prospective control identities without consuming global RNG."""

import random

from order_contract import scenarios as excluded_scenarios
from training_contract import COUNT, scenarios


def test_fixed_disjoint_orders_and_local_streams():
    before = random.getstate()
    first, second = scenarios(), scenarios()
    assert random.getstate() == before
    assert first == second and len(first) == COUNT
    assert len({c.cluster_id for c in first}) == COUNT
    assert len({c.scenario_id for c in first}) == COUNT
    assert all(c.relative_decks[0] == c.relative_decks[1] for c in first)
    assert not {c.relative_decks for c in first} & {c.relative_decks for c in excluded_scenarios()}
    assert len({seed for c in first for _, seed in c.stream_seeds}) == 2 * COUNT
