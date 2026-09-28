import pytest

from clasher.rl.deck_benchmark import (
    compare_game_records,
    deck_archetype_index,
    summarize_deck_records,
)


def test_deck_benchmark_reports_per_archetype_and_matchup() -> None:
    hog = ["a", "b", "c", "d", "e", "f", "g", "hog"]
    xbow = ["a", "b", "c", "d", "e", "f", "g", "xbow"]
    index = deck_archetype_index(
        [
            {"cards": hog, "archetype": "hog"},
            {"cards": xbow, "archetype": "x-bow"},
        ]
    )
    summary = summarize_deck_records(
        [
            {
                "candidate_deck": list(reversed(hog)),
                "opponent_deck": xbow,
                "outcome": "win",
                "candidate_crowns": 2,
                "opponent_crowns": 1,
            },
            {
                "candidate_deck": hog,
                "opponent_deck": xbow,
                "outcome": "loss",
                "candidate_crowns": 0,
                "opponent_crowns": 1,
            },
        ],
        archetypes_by_deck=index,
    )

    assert summary["archetypes"]["hog"] == {
        "games": 2,
        "wins": 1,
        "losses": 1,
        "draws": 0,
        "score_rate": 0.5,
        "crown_difference_per_game": 0.0,
        "distinct_candidate_decks": 1,
    }
    assert summary["matchups"]["hog_vs_x-bow"]["games"] == 2


def test_matched_record_comparison_is_fail_closed_on_regression() -> None:
    deck = ["a", "b", "c", "d", "e", "f", "g", "h"]
    baseline = [
        {
            "matchup_seed": 11,
            "candidate_player": 0,
            "candidate_deck": deck,
            "opponent_deck": deck,
            "outcome": "win",
            "candidate_crowns": 2,
            "opponent_crowns": 1,
        },
        {
            "matchup_seed": 11,
            "candidate_player": 1,
            "candidate_deck": deck,
            "opponent_deck": deck,
            "outcome": "loss",
            "candidate_crowns": 0,
            "opponent_crowns": 1,
        },
    ]
    candidate = [
        {**baseline[0], "outcome": "loss", "candidate_crowns": 0},
        {**baseline[1], "outcome": "win", "candidate_crowns": 2},
    ]

    comparison = compare_game_records(baseline, candidate)

    assert comparison["improvement_count"] == 1
    assert comparison["regression_count"] == 1
    assert not comparison["passes_strict_no_regression"]


def test_matched_record_comparison_requires_identical_games() -> None:
    with pytest.raises(ValueError, match="keys must match"):
        compare_game_records(
            [
                {
                    "matchup_seed": 11,
                    "candidate_player": 0,
                    "candidate_deck": list("abcdefgh"),
                    "opponent_deck": list("abcdefgh"),
                    "outcome": "win",
                    "candidate_crowns": 1,
                    "opponent_crowns": 0,
                }
            ],
            [],
        )
