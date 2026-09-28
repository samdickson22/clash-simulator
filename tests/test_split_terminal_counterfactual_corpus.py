from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from scripts.split_terminal_counterfactual_corpus import main


def test_counterfactual_split_is_game_disjoint_and_row_aligned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.npz"
    game_ids = np.asarray([0, 0, 1, 2, 3, 3], dtype=np.int64)
    values = np.arange(12, dtype=np.float32).reshape(6, 2)
    np.savez_compressed(source, game_ids=game_ids, values=values)
    report = tmp_path / "source.json"
    report.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "states": [
                    {
                        "game": int(game),
                        "tick": index,
                        "decisive_improvement": index % 2 == 0,
                        "base_score": float(index % 2),
                    }
                    for index, game in enumerate(game_ids)
                ],
                "games": [{"game": index} for index in range(4)],
            }
        ),
        encoding="utf-8",
    )
    train = tmp_path / "train.npz"
    validation = tmp_path / "validation.npz"
    train_report = tmp_path / "train.json"
    validation_report = tmp_path / "validation.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "split",
            "--input",
            str(source),
            "--report",
            str(report),
            "--train-out",
            str(train),
            "--train-report",
            str(train_report),
            "--validation-out",
            str(validation),
            "--validation-report",
            str(validation_report),
            "--validation-modulus",
            "2",
            "--validation-remainder",
            "1",
        ],
    )

    main()

    with np.load(train, allow_pickle=False) as train_payload:
        train_games = set(train_payload["game_ids"].tolist())
        assert train_payload["values"].shape[0] == 3
    with np.load(validation, allow_pickle=False) as validation_payload:
        validation_games = set(validation_payload["game_ids"].tolist())
        assert validation_payload["values"].shape[0] == 3
    assert train_games == {0, 2}
    assert validation_games == {1, 3}
    assert train_games.isdisjoint(validation_games)
    assert json.loads(train_report.read_text())["states_collected"] == 3
    assert json.loads(validation_report.read_text())["states_collected"] == 3
