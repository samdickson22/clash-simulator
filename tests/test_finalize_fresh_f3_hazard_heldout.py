from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.finalize_fresh_f3_hazard_heldout import (
    STRATEGY_OPPONENTS,
    _heldout_strategy_summary,
    finalize,
)


def _strategy(wins: dict[str, int], *, games: int = 4) -> dict[str, object]:
    return {
        "protocol": {"games_per_opponent": games},
        "results": {
            name: {
                "games": games,
                "wins": value,
                "losses": games - value,
                "draws": 0,
                "crown_diff_per_game": (2 * value - games) / games,
            }
            for name, value in wins.items()
        },
    }


def _evaluation(wins: int, games: int, *, seat0: int = 0, seat1: int = 0) -> dict[str, object]:
    return {
        "metrics": {
            "games": games,
            "wins": wins,
            "losses": games - wins,
            "draws": 0,
            "crown_diff_per_game": 0.0,
            "wins_as_player0": seat0,
            "wins_as_player1": seat1,
        }
    }


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_heldout_strategy_summary_accepts_exact_four_game_protocol() -> None:
    wins = {name: 2 for name in STRATEGY_OPPONENTS}
    summary = _heldout_strategy_summary(_strategy(wins))
    assert summary["wins"] == 12
    assert summary["losses"] == 12


@pytest.mark.parametrize("games", [3, 6])
def test_heldout_strategy_summary_rejects_other_protocol_sizes(games: int) -> None:
    wins = {name: min(2, games) for name in STRATEGY_OPPONENTS}
    with pytest.raises(ValueError, match="four games"):
        _heldout_strategy_summary(_strategy(wins, games=games))


def test_finalize_authorizes_candidate_at_exact_predeclared_boundaries(tmp_path: Path) -> None:
    root = tmp_path / "root"
    parent_wins = {
        "balanced": 1,
        "bridge-pressure": 2,
        "reactive-defense": 2,
        "slow-push": 1,
        "spell-control": 0,
        "split-lane": 2,
    }
    candidate_wins = {
        "balanced": 1,
        "bridge-pressure": 2,
        "reactive-defense": 3,
        "slow-push": 2,
        "spell-control": 2,
        "split-lane": 2,
    }
    _write(root / "parent" / "strategy.json", _strategy(parent_wins))
    _write(root / "candidate" / "strategy.json", _strategy(candidate_wins))
    _write(root / "parent" / "random24.metrics.json", _evaluation(9, 24))
    _write(root / "candidate" / "random24.metrics.json", _evaluation(12, 24))
    _write(
        root / "candidate" / "direct48.metrics.json",
        _evaluation(27, 48, seat0=15, seat1=12),
    )

    result = finalize(root, root / "decision.json")

    assert result["rejection_reasons"] == []
    assert result["expanded_safety_evaluation_authorized"] is True
    assert result["promotion_authorized"] is False
    assert result["selected"] == "candidate"
