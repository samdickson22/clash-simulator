from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_dagger_training_archetype_pools import build_pools


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value))


def _deck(name: str, archetype: str, win_condition: str, suffix: str) -> dict:
    return {
        "name": name,
        "archetype": archetype,
        "cards": [win_condition, "A", "B", "C", "D", "E", "F", suffix],
    }


def test_training_archetype_pools_exclude_whole_heldout_archetypes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    validation = tmp_path / "validation.json"
    heldout = tmp_path / "heldout.json"
    utilization = tmp_path / "utilization.json"
    output = tmp_path / "pools"
    manifest = tmp_path / "manifest.json"
    _write(
        source,
        {
            "decks": [
                _deck("hog-a", "hog", "HogRider", "G"),
                _deck("hog-b", "hog", "HogRider", "H"),
            ]
        },
    )
    _write(validation, {"decks": [_deck("eval-hog", "hog", "HogRider", "I")]})
    _write(heldout, {"decks": [_deck("eval-xbow", "x-bow", "Xbow", "J")]})
    _write(
        utilization,
        {
            "entries": [
                {
                    "archetype": "hog",
                    "designated_card": "HogRider",
                    "source_pool": "validation",
                },
                {
                    "archetype": "x-bow",
                    "designated_card": "Xbow",
                    "source_pool": "heldout",
                },
            ]
        },
    )

    result = build_pools(
        source_pool=source,
        validation_pool=validation,
        heldout_pool=heldout,
        utilization_manifest=utilization,
        output_dir=output,
        manifest_out=manifest,
    )

    assert result["heldout_archetypes"] == ["x-bow"]
    assert result["heldout_archetypes_in_source"] == []
    assert [row["archetype"] for row in result["training_archetypes"]] == ["hog"]
    pool = json.loads((output / "hog.json").read_text())
    assert len(pool["decks"]) == 2
    assert {deck["sampling_weight"] for deck in pool["decks"]} == {0.5}


def test_training_archetype_pools_fail_on_frozen_deck_overlap(
    tmp_path: Path,
) -> None:
    overlap = _deck("same", "hog", "HogRider", "G")
    source = tmp_path / "source.json"
    validation = tmp_path / "validation.json"
    heldout = tmp_path / "heldout.json"
    utilization = tmp_path / "utilization.json"
    _write(source, {"decks": [overlap]})
    _write(validation, {"decks": [overlap]})
    _write(heldout, {"decks": [_deck("x", "x-bow", "Xbow", "J")]})
    _write(
        utilization,
        {
            "entries": [
                {
                    "archetype": "hog",
                    "designated_card": "HogRider",
                    "source_pool": "validation",
                },
                {
                    "archetype": "x-bow",
                    "designated_card": "Xbow",
                    "source_pool": "heldout",
                },
            ]
        },
    )

    with pytest.raises(ValueError, match="overlaps a frozen evaluation deck"):
        build_pools(
            source_pool=source,
            validation_pool=validation,
            heldout_pool=heldout,
            utilization_manifest=utilization,
            output_dir=tmp_path / "pools",
            manifest_out=tmp_path / "manifest.json",
        )
