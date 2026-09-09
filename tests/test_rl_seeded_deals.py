import numpy as np
import torch

from clasher.rl.seeded_deals import SeededDealSchedule


def schedule(seed=1):
    own, opponent = torch.arange(8), torch.arange(8, 16)
    decks = torch.stack([torch.stack([own, opponent]), torch.stack([opponent, own])])
    return SeededDealSchedule(
        decks,
        torch.tensor([0, 1]),
        ["balanced|deck", "balanced|deck"],
        seed=seed,
        episodes=32,
    )


def test_deals_preserve_composition_pairing_and_reproducibility():
    first, second = schedule(), schedule()
    assert torch.equal(first.table, second.table)
    assert not torch.equal(first.table, schedule(2).table)
    assert torch.equal(first.table[:, 0], first.table[:, 1].flip(1))
    assert torch.equal(
        first.table[:, 0, 0].sort(-1).values, torch.arange(8).expand(32, -1)
    )
    assert torch.equal(
        first.table[:, 0, 1].sort(-1).values, torch.arange(8, 16).expand(32, -1)
    )
    assert len(set(first.scenario_ids_by_stream[0])) == 32
    assert first.scenario_ids_by_stream[0] == first.scenario_ids_by_stream[1]


def test_asynchronous_resets_are_ordinal_based_and_do_not_advance_other_rows():
    planned = schedule()
    initial = planned.initial_decks()
    next_decks = planned(0, torch.tensor([True, False]), None)
    assert torch.equal(next_decks[0], planned.table[1, 0])
    assert torch.equal(next_decks[1], initial[1])
    aligned = planned(900, torch.tensor([False, True]), None)
    assert torch.equal(aligned[0], aligned[1].flip(0))
    for _ in range(40):
        surplus = planned(0, torch.tensor([True, True]), None)
    assert torch.equal(surplus, planned.table[-1])


def test_deal_planning_does_not_change_policy_rng_state():
    torch.manual_seed(7)
    np.random.seed(7)
    torch_before = torch.get_rng_state().clone()
    numpy_before = np.random.get_state()
    schedule()
    assert torch.equal(torch_before, torch.get_rng_state())
    after = np.random.get_state()
    np.testing.assert_array_equal(numpy_before[1], after[1])
    assert numpy_before[2:] == after[2:]
