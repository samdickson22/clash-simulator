from __future__ import annotations

import pytest

from scripts.split_tv_royale_public_sidecars import _select_split_records


def test_select_split_records_is_ordered_and_requires_public_state() -> None:
    records = {
        "a": {"replay": "a", "public_state_v2": "a.npz"},
        "b": {"replay": "b", "public_state_v2": "b.npz"},
    }

    assert [
        row["replay"]
        for row in _select_split_records(["b", "a"], records_by_replay=records)
    ] == ["b", "a"]
    with pytest.raises(ValueError, match="nonempty and unique"):
        _select_split_records(["a", "a"], records_by_replay=records)
    with pytest.raises(ValueError, match="unavailable"):
        _select_split_records(["missing"], records_by_replay=records)
    with pytest.raises(ValueError, match="lack public-state"):
        _select_split_records(
            ["a"],
            records_by_replay={"a": {"replay": "a"}},
        )
