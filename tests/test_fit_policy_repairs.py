from __future__ import annotations

import json
from pathlib import Path

from scripts.fit_policy_repairs import _selected_repairs


def test_selected_repairs_preserve_deterministic_opponent_metadata(
    tmp_path: Path,
) -> None:
    payload = {
        "matchup_seed": 42,
        "candidate_player": 1,
        "opponent_checkpoint": "checkpoints/opponent.pt",
        "opponent_strategy": None,
        "winning_repairs": [
            {
                "tick": 96,
                "baseline_action": 12,
                "alternative_action": 34,
                "candidate_crowns": 1,
                "opponent_crowns": 0,
                "end_tick": 3600,
            }
        ],
    }
    source = tmp_path / "repair.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    repairs = _selected_repairs(str(source))

    assert repairs == [
        {
            **payload["winning_repairs"][0],
            "matchup_seed": 42,
            "candidate_player": 1,
            "opponent_checkpoint": "checkpoints/opponent.pt",
            "opponent_strategy": None,
        }
    ]
