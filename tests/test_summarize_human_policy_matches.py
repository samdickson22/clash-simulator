from __future__ import annotations

from scripts.summarize_human_policy_matches import summarize_human_matches


def _record(
    index: int,
    outcome: str,
    candidate_player: int,
    *,
    matchup_index: int | None = None,
) -> dict[str, object]:
    human_player = 1 - candidate_player
    matchup = index if matchup_index is None else matchup_index
    return {
        "checkpoint_sha256": "a" * 64,
        "session_seed": 100 + index,
        "match_number": 1,
        "human_player": human_player,
        "candidate_player": candidate_player,
        "candidate_outcome": outcome,
        "human_label": "tester-1",
        "human_ladder_label": "mid-ladder",
        "pacing_mode": "wall_clock_logic_ticks",
        "speed_locked": True,
        "logic_tick_seconds": 0.05,
        "human_deck": [f"common-{slot}" for slot in range(7)] + [f"h-{matchup}"],
        "candidate_deck": [f"common-{slot}" for slot in range(7)]
        + [f"c-{matchup}"],
    }


def test_human_match_summary_requires_balanced_diverse_confident_win() -> None:
    records = [
        _record(
            index,
            "win" if index < 18 else "loss",
            index % 2,
            matchup_index=index // 2,
        )
        for index in range(20)
    ]

    summary = summarize_human_matches(
        records,
        required_games=20,
        required_distinct_decks=8,
        required_score_rate=0.5,
    )

    assert summary["wins"] == 18
    assert summary["candidate_seats"]["0"]["games"] == 10
    assert summary["candidate_seats"]["1"]["games"] == 10
    assert summary["gates"]["balanced_matchup_seats"] is True
    assert summary["score_ci95_low"] > 0.5
    assert summary["passes_competitive_gate"] is True


def test_human_match_summary_rejects_unbalanced_seats() -> None:
    records = [_record(index, "win", 0) for index in range(20)]

    summary = summarize_human_matches(
        records,
        required_games=20,
        required_distinct_decks=8,
        required_score_rate=0.5,
    )

    assert summary["gates"]["balanced_candidate_seats"] is False
    assert summary["passes_competitive_gate"] is False


def test_human_match_summary_rejects_accelerated_legacy_records() -> None:
    records = [
        _record(index, "win", index % 2, matchup_index=index // 2)
        for index in range(20)
    ]
    records[0]["speed_locked"] = False

    summary = summarize_human_matches(
        records,
        required_games=20,
        required_distinct_decks=8,
        required_score_rate=0.5,
    )

    assert summary["gates"]["realtime_pacing"] is False
    assert summary["passes_competitive_gate"] is False


def test_human_match_summary_rejects_wrong_ladder_cohort() -> None:
    records = [
        _record(index, "win", index % 2, matchup_index=index // 2)
        for index in range(20)
    ]
    records[0]["human_ladder_label"] = "beginner"

    summary = summarize_human_matches(
        records,
        required_games=20,
        required_distinct_decks=8,
        required_score_rate=0.5,
    )

    assert summary["gates"]["required_human_ladder_cohort"] is False
    assert summary["passes_competitive_gate"] is False


def test_human_match_summary_rejects_unpaired_matchup_seats() -> None:
    records = [
        _record(index, "win", index % 2, matchup_index=index)
        for index in range(20)
    ]

    summary = summarize_human_matches(
        records,
        required_games=20,
        required_distinct_decks=8,
        required_score_rate=0.5,
    )

    assert summary["gates"]["balanced_candidate_seats"] is True
    assert summary["gates"]["balanced_matchup_seats"] is False
    assert summary["passes_competitive_gate"] is False
