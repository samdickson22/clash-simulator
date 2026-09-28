from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_weighted_counterfactual_sampling import audit_sampling


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fixture(tmp_path: Path, archetypes: list[str]) -> tuple[Path, Path]:
    pool = tmp_path / "pool.json"
    decks = []
    for index, archetype in enumerate(("a", "b")):
        decks.append(
            {
                "archetype": archetype,
                "cards": [f"{archetype}{slot}" for slot in range(8)],
                "sampling_weight": 1.0,
            }
        )
    _write_json(pool, {"decks": decks})
    shards = tmp_path / "shards"
    shards.mkdir()
    learner = [f"learner{slot}" for slot in range(8)]
    for game_id, archetype in enumerate(archetypes):
        opponent = [f"{archetype}{slot}" for slot in range(8)]
        controlled_player = game_id % 2
        game_decks = [learner, opponent]
        if controlled_player == 1:
            game_decks.reverse()
        _write_json(
            shards / f"game_{game_id:06d}.json",
            {
                "games": [
                    {
                        "game": game_id,
                        "controlled_player": controlled_player,
                        "decks": game_decks,
                    }
                ]
            },
        )
    return shards, pool


def test_audit_sampling_accepts_exact_balanced_ids(tmp_path: Path) -> None:
    shards, pool = _fixture(tmp_path, ["a", "b", "a", "b"])
    result = audit_sampling(
        shards=shards,
        opponent_pool=pool,
        games=4,
        maximum_total_variation=0.0,
        schema="test.v1",
    )
    assert result["passed"] is True
    assert result["candidate_seats"] == {"0": 2, "1": 2}
    assert result["observed_archetype_games"] == {"a": 2, "b": 2}
    assert result["total_variation"] == 0.0


def test_audit_sampling_rejects_missing_exact_id(tmp_path: Path) -> None:
    shards, pool = _fixture(tmp_path, ["a", "b", "a"])
    with pytest.raises(ValueError, match="game ids are incomplete"):
        audit_sampling(
            shards=shards,
            opponent_pool=pool,
            games=4,
            maximum_total_variation=1.0,
            schema="test.v1",
        )
