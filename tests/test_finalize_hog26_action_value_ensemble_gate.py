from __future__ import annotations

from copy import deepcopy

from scripts.finalize_hog26_action_value_ensemble_gate import (
    summarize_paired_reports,
)


def _reports(*, mode: str = "screen") -> list[dict[str, object]]:
    games_per_strategy = 8 if mode == "screen" else 16
    seed = 1164811 if mode == "screen" else 1165811
    reports: list[dict[str, object]] = []
    for strategy_index, strategy in enumerate(
        (
            "bridge-pressure",
            "slow-push",
            "balanced",
            "reactive-defense",
            "spell-control",
            "split-lane",
        )
    ):
        games = []
        for game in range(games_per_strategy):
            improve = strategy_index == 0 and game < (2 if mode == "screen" else 4)
            baseline = {
                "game": game,
                "seed": seed + game * 1009,
                "repaired": False,
                "candidate_player": game % 2,
                "candidate_deck": ["HogRider"],
                "opponent_deck": [strategy],
                "result": "loss" if improve else "draw",
                "candidate_crowns": 0,
                "opponent_crowns": 1 if improve else 0,
            }
            repaired = {
                **baseline,
                "repaired": True,
                "result": "win" if improve else "draw",
                "candidate_crowns": 2 if improve else 0,
                "opponent_crowns": 0,
            }
            games.extend((baseline, repaired))
        reports.append(
            {
                "schema_version": 1,
                "policy": "policy.pt",
                "policy_sha256": "a" * 64,
                "action_value": "ensemble.json",
                "action_value_sha256": "b" * 64,
                "action_value_mode": "controller",
                "decks_sha256": "c" * 64,
                "learner_sampling_decks_path": "hog26.json",
                "learner_sampling_decks_sha256": "d" * 64,
                "opponent_sampling_decks_path": f"{mode}.json",
                "opponent_sampling_decks_sha256": "e" * 64,
                "strategy": strategy,
                "seed": seed,
                "game_offset": 0,
                "decision_interval": 8,
                "max_ticks": 6000,
                "max_candidates": 6,
                "minimum_tick": 256,
                "query_stride": 16,
                "games": games,
            }
        )
    return reports


def test_hog26_action_value_screen_accepts_paired_multi_strategy_gain() -> None:
    result = summarize_paired_reports(_reports(), mode="screen")

    assert result["passed"]
    assert result["games"] == 48
    assert result["win_to_loss"] == 0
    assert result["loss_to_win"] == 2
    assert result["crown_delta"] == 6
    assert min(result["strategy_crown_deltas"].values()) == 0


def test_hog26_action_value_screen_rejects_one_win_to_loss() -> None:
    reports = deepcopy(_reports())
    rows = reports[1]["games"]
    assert isinstance(rows, list)
    rows[0]["result"] = "win"
    rows[1]["result"] = "loss"

    result = summarize_paired_reports(reports, mode="screen")

    assert not result["passed"]
    assert result["win_to_loss"] == 1


def test_hog26_action_value_screen_rejects_missing_strategy() -> None:
    reports = _reports()[:-1]

    try:
        summarize_paired_reports(reports, mode="screen")
    except ValueError as error:
        assert "one report" in str(error)
    else:
        raise AssertionError("incomplete strategy coverage should fail closed")


def test_hog26_action_value_screen_rejects_stale_seed() -> None:
    reports = deepcopy(_reports())
    reports[0]["seed"] = 1164801

    try:
        summarize_paired_reports(reports, mode="screen")
    except ValueError as error:
        assert "seed" in str(error)
    else:
        raise AssertionError("stale gameplay seeds should fail closed")


def test_hog26_action_value_screen_rejects_checkpoint_hash_drift() -> None:
    reports = deepcopy(_reports())
    reports[3]["action_value_sha256"] = "f" * 64

    try:
        summarize_paired_reports(reports, mode="screen")
    except ValueError as error:
        assert "action-value hashes" in str(error)
    else:
        raise AssertionError("checkpoint hash drift should fail closed")


def test_hog26_action_value_quarantine_accepts_frozen_contract() -> None:
    result = summarize_paired_reports(_reports(mode="quarantine"), mode="quarantine")

    assert result["passed"]
    assert result["games"] == 96
    assert result["loss_to_win"] == 4
    assert result["crown_delta"] == 12
    assert result["score_delta_bootstrap_ci95"][0] > 0.0


def test_hog26_action_value_rejects_hidden_strategy_regression() -> None:
    reports = deepcopy(_reports())
    rows = reports[1]["games"]
    assert isinstance(rows, list)
    rows[1]["result"] = "loss"

    result = summarize_paired_reports(reports, mode="screen")

    assert not result["passed"]
    assert result["score_delta_mean"] > 0.0
    assert result["strategy_score_deltas"]["slow-push"] < 0.0
