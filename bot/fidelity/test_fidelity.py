import json
from types import SimpleNamespace as NS

import pytest

from bot.fidelity.fixture import load_fixture
from bot.fidelity.score import assign, pair_units, score


def unit(side, root, first, rows, slot=None):
    return NS(side=side, root=root, tower_slot=slot, first_tick=first, rows=rows)


def test_assign_minimises_total_distance_and_breaks_ties_by_hp():
    assert sorted(assign([(0, 0), (10, 0)], [(10, 0), (0, 0)], [1, 1], [1, 1])) == [(0, 1), (1, 0)]
    # two members on one point: hp decides
    assert sorted(assign([(0, 0), (0, 0)], [(0, 0), (0, 0)], [100, 50], [50, 100])) == [(0, 1), (1, 0)]


def test_pair_groups_prefer_same_size_then_time_and_leave_extras_unmatched():
    truth = {1: unit(0, 7, 10, {10: (0, 0, 5)}), 2: unit(0, 7, 10, {10: (100, 0, 5)})}
    sim = {
        11: unit(0, 7, 12, {12: (0, 0, 5)}),  # pool of size 1, near in time
        21: unit(0, 7, 15, {15: (0, 0, 5)}), 22: unit(0, 7, 15, {15: (100, 0, 5)}),  # same size
        31: unit(1, 7, 10, {10: (0, 0, 5)}),  # other side: never pairs
    }
    pairs = set(pair_units(truth, sim))
    assert (1, 21) in pairs and (2, 22) in pairs
    assert (None, 11) in pairs and (None, 31) in pairs


def test_score_counts_alive_mismatch_as_miss_and_towers_apart():
    truth = {1: unit(0, 7, 0, {0: (0, 0, 10), 1: (0, 0, 10)}), 9: unit(0, -1, 0, {0: (9000, 3000, 1)}, slot=0)}
    sim = {5: unit(0, 7, 0, {0: (200, 0, 10)}), 8: unit(0, -1, 0, {0: (9000, 3000, 1)}, slot=0)}
    r = score(truth, sim, [0, 1], lambda c: str(c))
    nt = r["no_towers"]
    assert nt["unit_ticks"] == 2 and nt["w250"] == 1 and nt["alive_mismatch"] == 1 and nt["hp_exact"] == 1
    assert r["towers"]["unit_ticks"] == 1 and r["towers"]["w250"] == 1


@pytest.mark.parametrize("split", ["heldout", "smoke", None])
def test_loader_refuses_non_trainval_before_opening(tmp_path, split):
    d = tmp_path / "ep1"
    d.mkdir()  # no files: refusal must happen before any read
    splits = {} if split is None else {"ep1": split}
    with pytest.raises(PermissionError):
        load_fixture(d, splits)
