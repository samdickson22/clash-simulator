from __future__ import annotations

from scripts.finalize_fresh_f3_hazard_expanded_safety import (
    _clustered_bootstrap,
    _gate_reasons,
)


def _outcome(wins: float = 100.0, crowns: float = 10.0) -> dict[str, float]:
    return {
        "games": 216.0,
        "wins": wins,
        "losses": 216.0 - wins,
        "draws": 0.0,
        "score": wins,
        "crown_difference": crowns,
    }


def _passing_inputs() -> dict[str, object]:
    parent = _outcome(100.0, 10.0)
    candidate = _outcome(104.0, 16.0)
    blocks = {
        f"block{index}": {
            "parent": _outcome(33.0, 3.0),
            "candidate": _outcome(34.0, 4.0),
        }
        for index in range(3)
    }
    workloads = {
        "random12": {"parent": _outcome(18.0, 0.0), "candidate": _outcome(17.0, -2.0)},
        "balanced12": {"parent": _outcome(18.0, 0.0), "candidate": _outcome(19.0, 1.0)},
    }
    behavior = {
        "parent": {
            "noop_when_playable": 0.93,
            "placement_rate": 0.05,
            "defense_event_success_rate": 0.40,
            "defense_event_mean_outcome": -0.10,
            "defensive_action_rate_when_threatened": 0.06,
            "incoming_tower_danger_mean": 0.10,
        },
        "candidate": {
            "noop_when_playable": 0.94,
            "placement_rate": 0.05,
            "defense_event_success_rate": 0.38,
            "defense_event_mean_outcome": -0.10,
            "defensive_action_rate_when_threatened": 0.05,
            "incoming_tower_danger_mean": 0.10,
        },
    }
    human = {
        "parent": {
            "predicted_play_rate": 0.02,
            "play_average_precision": 0.04,
            "play_roc_auc": 0.72,
            "play_brier": 0.01,
            "play_ece_10_bin": 0.01,
            "conditional_card_slot_accuracy": 0.40,
            "play_samples": 1000.0,
        },
        "candidate": {
            "predicted_play_rate": 0.02,
            "play_average_precision": 0.038,
            "play_roc_auc": 0.71,
            "play_brier": 0.015,
            "play_ece_10_bin": 0.02,
            "conditional_card_slot_accuracy": 0.39,
            "play_samples": 1000.0,
        },
    }
    return {
        "parent": parent,
        "candidate": candidate,
        "blocks": blocks,
        "workloads": workloads,
        "behavior": behavior,
        "paired": {"score_delta_mean": 0.02},
        "direct": {
            "wins": 52.0,
            "losses": 44.0,
            "draws": 0.0,
            "wins_as_player0": 28.0,
            "wins_as_player1": 24.0,
            "crown_difference": 1.0,
        },
        "human": human,
    }


def test_expanded_safety_gate_accepts_exact_predeclared_boundaries() -> None:
    assert _gate_reasons(**_passing_inputs()) == []  # type: ignore[arg-type]


def test_expanded_safety_gate_rejects_block_and_direct_seat_regressions() -> None:
    inputs = _passing_inputs()
    inputs["blocks"]["block1"]["candidate"]["wins"] = 32.0  # type: ignore[index]
    inputs["direct"]["wins_as_player1"] = 23.0  # type: ignore[index]
    reasons = _gate_reasons(**inputs)  # type: ignore[arg-type]
    assert "external_block_win_regression:block1" in reasons
    assert "direct96_losing_seat" in reasons


def test_clustered_bootstrap_is_deterministic_and_reports_matchup_units() -> None:
    first = _clustered_bootstrap([0.0, 0.5, 0.5, 1.0], [-1.0, 0.0, 1.0, 2.0])
    second = _clustered_bootstrap([0.0, 0.5, 0.5, 1.0], [-1.0, 0.0, 1.0, 2.0])
    assert first == second
    assert first["clusters"] == 4.0
    assert first["score_delta_mean"] == 0.5
