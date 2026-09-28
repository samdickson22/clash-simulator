from __future__ import annotations

import pytest

from scripts.audit_action_value_card_utilization import audit_reports


def _game(game: int, repaired: bool, *, uses: bool, tile: int) -> dict[str, object]:
    return {
        "game": game,
        "seed": 1000 + game,
        "repaired": repaired,
        "candidate_player": game % 2,
        "candidate_deck": ["HogRider", "Cannon"],
        "opponent_deck": ["Giant", "Arrows"],
        "card_plays": {"HogRider": 2 if uses else 0},
        "repair_rows": (
            []
            if not repaired or not uses
            else [
                {
                    "base": {"action": 2304, "kind": "no-op"},
                    "selected": {
                        "action": tile,
                        "kind": "placement",
                        "card": "HogRider",
                        "tile": tile,
                    },
                }
            ]
        ),
    }


def _report(strategy: str, *, collapse: bool = False) -> dict[str, object]:
    games: list[dict[str, object]] = []
    for game in range(4):
        games.append(_game(game, False, uses=game == 0, tile=1))
        games.append(
            _game(
                game,
                True,
                uses=game != 3,
                tile=7 if collapse or game % 2 == 0 else 19,
            )
        )
    return {"strategy": strategy, "games": games}


def _audit(reports: list[dict[str, object]]) -> dict[str, object]:
    return audit_reports(
        reports,
        required_card="HogRider",
        minimum_game_usage_rate=0.75,
        minimum_strategy_game_usage_rate=0.50,
        minimum_plays_per_game=1.0,
        minimum_selected_overrides=4,
        minimum_override_tiles=2,
        maximum_override_tile_share=0.75,
    )


def test_utilization_gate_accepts_cross_strategy_use_and_tile_diversity() -> None:
    result = _audit([_report("balanced"), _report("slow-push")])
    assert result["passed"] is True
    assert result["repaired"]["game_usage_rate"] == 0.75
    assert result["selected_overrides"] == 6
    assert result["selected_override_tile_count"] == 2


def test_utilization_gate_rejects_single_tile_collapse() -> None:
    result = _audit([_report("balanced", collapse=True), _report("slow-push", collapse=True)])
    assert result["passed"] is False
    assert result["dominant_override_tile_share"] == 1.0


def test_utilization_gate_ignores_retained_base_card_queries() -> None:
    report = _report("balanced")
    repaired = next(row for row in report["games"] if row["repaired"])
    repaired["repair_rows"].append(
        {
            "base": {
                "action": 7,
                "kind": "placement",
                "card": "HogRider",
                "tile": 7,
            },
            "selected": {
                "action": 7,
                "kind": "placement",
                "card": "HogRider",
                "tile": 7,
            },
        }
    )

    result = _audit([report, _report("slow-push")])

    assert result["selected_overrides"] == 6


def test_utilization_gate_rejects_missing_pairs_and_required_card() -> None:
    report = _report("balanced")
    report["games"] = list(report["games"])[1:]
    with pytest.raises(ValueError, match="paired arm"):
        _audit([report])

    report = _report("balanced")
    first = next(iter(report["games"]))
    first["candidate_deck"] = ["Cannon"]
    with pytest.raises(ValueError, match="differ at candidate_deck"):
        _audit([report])
