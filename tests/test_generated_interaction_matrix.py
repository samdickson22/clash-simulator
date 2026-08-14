from collections import Counter
from itertools import islice, pairwise

import pytest

from clasher.interaction_matrix import (
    EVENT_FAMILIES,
    GEOMETRIES,
    enabled_troop_cards,
    iter_one_v_one_cases,
    iter_two_v_two_cases,
    matrix_manifest,
    one_v_one_case_count,
    shard_range,
    team_composition_count,
    two_v_two_composition_count,
)


def test_enabled_interaction_catalog_is_data_driven_and_stable():
    cards = enabled_troop_cards()

    assert len(cards) == 46
    assert cards == tuple(sorted(cards))
    assert "ArcherQueen" in cards
    assert "Cannon" not in cards
    assert "Fireball" not in cards


def test_one_v_one_matrix_is_exhaustive_ordered_mirrored_and_dual_engine():
    cards = enabled_troop_cards()
    cases = list(iter_one_v_one_cases(cards))

    assert len(cases) == one_v_one_case_count(len(cards)) == 8_464
    coverage = Counter(
        (case.team_0, case.team_1, case.fast_path, case.mirrored)
        for case in cases
    )
    assert len(coverage) == len(cases)
    assert {case.fast_path for case in cases} == {False, True}
    assert {case.mirrored for case in cases} == {False, True}


def test_two_v_two_matrix_exhausts_unordered_compositions_only():
    cards = enabled_troop_cards()
    cases = list(islice(iter_two_v_two_cases(cards), 5_000))

    assert team_composition_count(len(cards)) == 1_081
    assert two_v_two_composition_count(len(cards)) == 584_821
    compositions = {(case.team_0, case.team_1) for case in cases}
    assert len(compositions) == len(cases)
    assert {case.geometry for case in cases} == set(GEOMETRIES)
    assert {case.event_family for case in cases} == set(EVENT_FAMILIES)


def test_two_v_two_iterator_builds_catalog_once(monkeypatch):
    from clasher import interaction_matrix

    calls = 0
    original = interaction_matrix._team_compositions

    def counted(cards):
        nonlocal calls
        calls += 1
        return original(cards)

    monkeypatch.setattr(interaction_matrix, "_team_compositions", counted)

    cases = list(islice(iter_two_v_two_cases(("A", "B", "C")), 10))

    assert len(cases) == 10
    assert calls == 1


@pytest.mark.parametrize("total,shards", [(8_464, 32), (584_821, 256)])
def test_shards_are_contiguous_nonoverlapping_and_complete(total, shards):
    ranges = [shard_range(total, index, shards) for index in range(shards)]

    assert ranges[0].start == 0
    assert ranges[-1].stop == total
    assert all(left.stop == right.start for left, right in pairwise(ranges))
    assert sum(item.size for item in ranges) == total


def test_manifest_reports_exact_and_systematic_coverage_separately():
    manifest = matrix_manifest()
    one_v_one = manifest["one_v_one"]
    two_v_two = manifest["two_v_two"]

    assert one_v_one["case_count"] == 8_464
    assert two_v_two["case_count"] == 584_821
    assert "systematic_not_exhaustive_axes" in two_v_two
    assert "systematic_not_exhaustive_axes" not in one_v_one
