import json
from pathlib import Path

from scripts.finalize_fresh_f1_legacy_replication import finalize

OPPONENTS = (
    "balanced",
    "bridge-pressure",
    "reactive-defense",
    "slow-push",
    "spell-control",
    "split-lane",
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_replication_requires_combined_gain_and_no_regression(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    _write(
        first,
        {
            "summaries": {
                "parent": {"strategy": {"wins": 14}},
                "legacy": {"strategy": {"wins": 15}},
            }
        },
    )
    root = tmp_path / "root"
    for arm, wins in (("parent", 2), ("candidate", 3)):
        _write(
            root / arm / "strategy.json",
            {
                "results": {
                    name: {
                        "games": 6,
                        "wins": wins,
                        "losses": 6 - wins,
                        "draws": 0,
                        "crown_diff_per_game": 0,
                    }
                    for name in OPPONENTS
                }
            },
        )
        _write(
            root / arm / "random12.metrics.json",
            {
                "metrics": {
                    "games": 12,
                    "wins": 7,
                    "losses": 5,
                    "draws": 0,
                    "crown_diff_per_game": 0,
                }
            },
        )
        _write(
            root / arm / "human32.json",
            {
                "results": [
                    {
                        "predicted_play_rate": 0.5,
                        "played_card_slot_accuracy": 0.3,
                        "conditional_card_slot_accuracy": 0.4,
                        "play_average_precision": 0.1,
                    }
                ]
            },
        )
    _write(
        root / "candidate" / "direct12.metrics.json",
        {
            "metrics": {
                "games": 12,
                "wins": 7,
                "losses": 5,
                "draws": 0,
                "crown_diff_per_game": 0,
            }
        },
    )
    _write(root / "training_stability.json", {"passes": True})
    result = finalize(first, root, tmp_path / "decision.json")
    assert result["combined_strategy_win_gain"] == 7
    assert result["heldout_evaluation_authorized"] is True
