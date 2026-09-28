from __future__ import annotations

from clasher.data import CardDataLoader
from scripts.evaluate_win_condition_utilization import (
    primary_tower_pressure_cards,
    promotion_gate,
    summarize_utilization,
    tower_pressure_score,
)


def _row(
    *,
    game: int,
    decision: int,
    seat: int,
    elixir: float,
    hog_probability: float,
    play_hog: bool = False,
) -> dict:
    return {
        "game": game,
        "game_decision": decision,
        "candidate_player": seat,
        "hand": ["HogRider", "Musketeer", "Skeletons", "IceSpirit"],
        "elixir": elixir,
        "slot": 0 if play_hog else None,
        "is_no_op": not play_hog,
        "is_ability": False,
        "action_type_probabilities": [
            hog_probability,
            0.0,
            0.0,
            0.0,
            1.0 - hog_probability,
            0.0,
        ],
    }


def test_utilization_counts_affordable_windows_and_hand_locks() -> None:
    decisions = [
        _row(game=0, decision=0, seat=0, elixir=3.0, hog_probability=0.0),
        _row(game=0, decision=1, seat=0, elixir=4.0, hog_probability=0.2),
        _row(game=0, decision=2, seat=0, elixir=4.5, hog_probability=0.3),
        _row(
            game=0,
            decision=3,
            seat=0,
            elixir=5.0,
            hog_probability=0.4,
            play_hog=True,
        ),
        _row(game=1, decision=0, seat=1, elixir=4.0, hog_probability=0.1),
        _row(game=1, decision=1, seat=1, elixir=3.0, hog_probability=0.0),
        _row(game=1, decision=2, seat=1, elixir=4.0, hog_probability=0.1),
    ]
    games = [
        {
            "game": 0,
            "candidate_player": 0,
            "candidate_deck": ["HogRider", "Musketeer", "Skeletons", "IceSpirit"],
        },
        {
            "game": 1,
            "candidate_player": 1,
            "candidate_deck": ["HogRider", "Musketeer", "Skeletons", "IceSpirit"],
        },
    ]

    report = summarize_utilization(decisions, games)

    assert report["games"] == 2
    assert report["zero_use_games"] == 1
    assert report["affordable_windows"] == 3
    assert report["converted_windows"] == 1
    assert report["by_seat"]["0"]["zero_use_rate"] == 0.0
    assert report["by_seat"]["1"]["zero_use_rate"] == 1.0
    assert report["per_game"][0]["max_continuous_hand_seconds"] == 1.6


def test_primary_pressure_role_excludes_low_damage_kiting_tank() -> None:
    loader = CardDataLoader()

    selected = primary_tower_pressure_cards(["HogRider", "IceGolem"], loader)

    assert selected == ["HogRider"]
    assert tower_pressure_score("HogRider", loader) > 5.0 * tower_pressure_score(
        "IceGolem", loader
    )
    assert tower_pressure_score("Musketeer", loader) == 0.0


def test_designated_win_condition_supports_non_building_target_cards() -> None:
    cards = ("Graveyard", "Xbow", "Miner")
    games = []
    decisions = []
    for game, card in enumerate(cards):
        games.append(
            {
                "game": game,
                "candidate_player": game % 2,
                "candidate_deck": [card, "Musketeer", "Skeletons", "IceSpirit"],
            }
        )
        decisions.append(
            {
                "game": game,
                "game_decision": 0,
                "hand": [card, "Musketeer", "Skeletons", "IceSpirit"],
                "elixir": 10.0,
                "slot": 0,
                "is_no_op": False,
                "is_ability": False,
                "action_type_probabilities": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            }
        )

    report = summarize_utilization(
        decisions,
        games,
        role="designated_win_condition",
        designated_cards=set(cards),
    )

    assert report["designated_cards"] == sorted(cards)
    assert report["games"] == 3
    assert report["plays"] == 3
    assert set(report["by_card"]) == set(cards)


def test_promotion_gate_requires_both_seats() -> None:
    report = {
        "zero_use_rate": 0.1,
        "window_conversion_rate": 0.5,
        "by_seat": {
            "0": {"games": 5, "zero_use_rate": 0.0, "window_conversion_rate": 0.5},
            "1": {"games": 5, "zero_use_rate": 0.2, "window_conversion_rate": 0.5},
        },
    }

    gate = promotion_gate(
        report,
        max_zero_use_rate=0.1,
        min_window_conversion_rate=0.25,
        min_games_per_seat=5,
    )

    assert not gate["passed"]
    assert not gate["checks"]["both_seats_zero_use_rate"]
