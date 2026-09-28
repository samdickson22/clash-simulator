from __future__ import annotations

from scripts.select_tv_royale_cycle_event_audit import select_stratified_events


def test_selection_is_deterministic_stratified_and_excludes_gold() -> None:
    events = [
        {
            "event_id": f"event-{index}",
            "timestamp_ms": index * 10_000,
            "player_id": index % 2,
            "play_confirmed": True,
            "identity_valid": True,
        }
        for index in range(16)
    ]
    gold = [{"timestamp_ms": 40_000, "player_id": 0, "play_valid": True}]

    first = select_stratified_events(events, count=8, seed=7, excluded=gold)
    second = select_stratified_events(events, count=8, seed=7, excluded=gold)

    assert first == second
    assert len(first) == 8
    assert {row["player_id"] for row in first} == {0, 1}
    assert all(row["timestamp_ms"] != 40_000 for row in first)


def test_selection_rejects_nonpositive_count() -> None:
    try:
        select_stratified_events([], count=0, seed=1)
    except ValueError as error:
        assert "positive" in str(error)
    else:
        raise AssertionError("nonpositive count should fail")
