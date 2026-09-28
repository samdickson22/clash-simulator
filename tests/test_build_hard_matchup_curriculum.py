from __future__ import annotations

import json

from scripts.build_hard_matchup_curriculum import build_curriculum


def test_build_curriculum_keeps_only_losses_and_weights_crown_deficit(tmp_path):
    path = tmp_path / "reactive-defense.json"
    base = {
        "candidate_deck": [f"learner-{index}" for index in range(8)],
        "opponent_deck": [f"opponent-{index}" for index in range(8)],
        "matchup_seed": 101,
        "candidate_player": 0,
    }
    path.write_text(
        json.dumps(
            [
                {
                    **base,
                    "outcome": "loss",
                    "candidate_crowns": 0,
                    "opponent_crowns": 2,
                },
                {
                    **base,
                    "outcome": "win",
                    "candidate_crowns": 1,
                    "opponent_crowns": 0,
                },
            ]
        ),
        encoding="utf-8",
    )

    result = build_curriculum([path])

    assert result["metadata"]["source_games"] == 2
    assert result["metadata"]["source_losses"] == 1
    assert result["metadata"]["losses_by_strategy"] == {"reactive-defense": 1}
    assert len(result["matchups"]) == 1
    assert result["matchups"][0]["weight"] == 3.0
