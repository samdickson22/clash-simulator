from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_win_condition_utilization_matrix import (
    WIN_CONDITION_SPECS,
    build_matrix,
)


def _write_pool(path: Path, source: str) -> None:
    decks = []
    for spec in WIN_CONDITION_SPECS:
        if spec.source != source:
            continue
        decks.append(
            {
                "name": f"{spec.archetype} base",
                "archetype": spec.archetype,
                "source": "project-base",
                "substitutions": 0,
                "cards": [
                    spec.card,
                    "Musketeer",
                    "Skeletons",
                    "IceSpirit",
                    "Fireball",
                    "Log",
                    "Cannon",
                    "Knight",
                ],
            }
        )
    path.write_text(json.dumps({"decks": decks}), encoding="utf-8")


def test_build_matrix_covers_all_designated_archetypes(tmp_path: Path) -> None:
    validation = tmp_path / "validation.json"
    heldout = tmp_path / "heldout.json"
    output = tmp_path / "matrix"
    _write_pool(validation, "validation")
    _write_pool(heldout, "heldout")

    result = build_matrix(
        validation_path=validation,
        heldout_path=heldout,
        output_dir=output,
    )

    assert len(result["entries"]) == len(WIN_CONDITION_SPECS) == 12
    assert {row["designated_card"] for row in result["entries"]} == {
        spec.card for spec in WIN_CONDITION_SPECS
    }
    for row in result["entries"]:
        payload = json.loads(Path(row["deck_pool"]).read_text(encoding="utf-8"))
        assert payload["decks"][0]["cards"][0] == row["designated_card"]


def test_build_matrix_rejects_missing_designated_card(tmp_path: Path) -> None:
    validation = tmp_path / "validation.json"
    heldout = tmp_path / "heldout.json"
    _write_pool(validation, "validation")
    _write_pool(heldout, "heldout")
    payload = json.loads(heldout.read_text(encoding="utf-8"))
    payload["decks"] = [
        row for row in payload["decks"] if row["archetype"] != "x-bow"
    ]
    heldout.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="x-bow/Xbow"):
        build_matrix(
            validation_path=validation,
            heldout_path=heldout,
            output_dir=tmp_path / "matrix",
        )
    assert not (tmp_path / "matrix").exists()


def test_build_matrix_refuses_to_overwrite_outputs(tmp_path: Path) -> None:
    validation = tmp_path / "validation.json"
    heldout = tmp_path / "heldout.json"
    output = tmp_path / "matrix"
    _write_pool(validation, "validation")
    _write_pool(heldout, "heldout")
    build_matrix(
        validation_path=validation,
        heldout_path=heldout,
        output_dir=output,
    )

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        build_matrix(
            validation_path=validation,
            heldout_path=heldout,
            output_dir=output,
        )
