from __future__ import annotations

from scripts.join_tv_royale_hud_clusters_to_actions import select_cycle_transition


def test_cycle_transition_prefers_next_entering_changed_slot() -> None:
    assert select_cycle_transition(
        [10, 11, 12, 13, 14], [10, 11, 14, 15, 16]
    ) == (2, "unique_next_enters_changed_slot")


def test_cycle_transition_falls_back_only_for_one_changed_slot() -> None:
    assert select_cycle_transition(
        [10, 11, 12, 13, 14], [10, 11, 12, 99, 14]
    ) == (3, "unique_changed_slot_without_next_confirmation")
    assert (
        select_cycle_transition([10, 11, 12, 13, 14], [99, 98, 12, 13, 14])
        is None
    )
