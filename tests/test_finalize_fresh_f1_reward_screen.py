from __future__ import annotations

import json
from pathlib import Path

from scripts.finalize_fresh_f1_reward_screen import finalize

OPPONENTS = (
    "balanced",
    "bridge-pressure",
    "reactive-defense",
    "slow-push",
    "spell-control",
    "split-lane",
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _populate(tmp_path: Path, *, candidate_wins: int) -> tuple[Path, Path, Path]:
    root = tmp_path / "reports"
    checkpoints = tmp_path / "checkpoints"
    parent = tmp_path / "parent.pt"
    parent.write_bytes(b"parent")
    for arm in ("parent", "legacy", "gamma", "gamma_noleak"):
        if arm != "parent":
            checkpoint = checkpoints / arm / "policy_v2_update_000020.pt"
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            checkpoint.write_bytes(arm.encode())
            _write(root / arm / "training_stability.json", {"passes": True})
        wins = 3 if arm == "parent" else candidate_wins
        _write(
            root / arm / "strategy.json",
            {
                "results": {
                    name: {
                        "games": 6,
                        "wins": wins,
                        "losses": 6 - wins,
                        "draws": 0,
                        "crown_diff_per_game": float(wins - 3),
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
                    "wins": 8,
                    "losses": 4,
                    "draws": 0,
                    "crown_diff_per_game": 0.5,
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
        if arm != "parent":
            _write(
                root / arm / "direct12.metrics.json",
                {
                    "metrics": {
                        "games": 12,
                        "wins": 7,
                        "losses": 5,
                        "draws": 0,
                        "crown_diff_per_game": 0.2,
                    }
                },
            )
    return root, checkpoints, parent


def test_finalizer_promotes_strictly_better_candidate(tmp_path: Path) -> None:
    root, checkpoints, parent = _populate(tmp_path, candidate_wins=4)
    result = finalize(root, checkpoints, parent, tmp_path / "decision.json")
    assert result["selected"] in {"legacy", "gamma", "gamma_noleak"}
    assert result["candidate_promoted"] is True


def test_finalizer_retains_parent_without_strategy_gain(tmp_path: Path) -> None:
    root, checkpoints, parent = _populate(tmp_path, candidate_wins=3)
    result = finalize(root, checkpoints, parent, tmp_path / "decision.json")
    assert result["selected"] == "parent"
    assert result["candidate_promoted"] is False
