"""Build one frozen evaluation deck for each major policy win condition."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, NamedTuple


class WinConditionSpec(NamedTuple):
    archetype: str
    card: str
    source: str


WIN_CONDITION_SPECS = (
    WinConditionSpec("balloon", "Balloon", "validation"),
    WinConditionSpec("bridge-spam", "BattleRam", "validation"),
    WinConditionSpec("giant", "Giant", "validation"),
    WinConditionSpec("golem", "Golem", "validation"),
    WinConditionSpec("hog", "HogRider", "validation"),
    WinConditionSpec("log-bait", "GoblinBarrel", "validation"),
    WinConditionSpec("miner", "Miner", "validation"),
    WinConditionSpec("wall-breakers", "Wallbreakers", "validation"),
    WinConditionSpec("graveyard", "Graveyard", "heldout"),
    WinConditionSpec("lava-hound", "LavaHound", "heldout"),
    WinConditionSpec("royal-hogs", "RoyalHogs", "heldout"),
    WinConditionSpec("x-bow", "Xbow", "heldout"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"deck pool must be an object: {path}")
    return payload


def _atomic_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _selection_key(row: dict[str, Any]) -> tuple[int, int, str]:
    return (
        0 if row.get("source") == "project-base" else 1,
        int(row.get("substitutions", 999)),
        str(row.get("name", "")),
    )


def build_matrix(
    *,
    validation_path: Path,
    heldout_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    validation_path = validation_path.resolve()
    heldout_path = heldout_path.resolve()
    sources = {
        "validation": _object(validation_path),
        "heldout": _object(heldout_path),
    }
    output_dir = output_dir.resolve()
    manifest_path = output_dir / "manifest.json"
    expected_paths = [
        output_dir / f"{spec.archetype.replace('-', '_')}.json"
        for spec in WIN_CONDITION_SPECS
    ]
    existing = [path for path in (*expected_paths, manifest_path) if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite win-condition matrix outputs: "
            + ", ".join(str(path) for path in existing)
        )

    selections: list[
        tuple[WinConditionSpec, Path, dict[str, Any], list[str]]
    ] = []
    for spec, output in zip(WIN_CONDITION_SPECS, expected_paths, strict=True):
        raw_decks = sources[spec.source].get("decks")
        if not isinstance(raw_decks, list):
            raise TypeError(f"{spec.source} pool lacks a deck array")
        matches = [
            row
            for row in raw_decks
            if isinstance(row, dict)
            and row.get("archetype") == spec.archetype
            and spec.card in row.get("cards", ())
        ]
        if not matches:
            raise ValueError(
                f"no {spec.source} deck contains {spec.archetype}/{spec.card}"
            )
        selected = min(matches, key=_selection_key)
        cards = [str(card) for card in selected.get("cards", ())]
        if len(cards) != 8 or len(set(cards)) != 8:
            raise ValueError(f"selected deck is not eight unique cards: {spec.archetype}")
        selections.append((spec, output, selected, cards))

    output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for spec, output, selected, cards in selections:
        deck_payload = {
            "schema_version": 1,
            "metadata": {
                "purpose": "win_condition_utilization_evaluation",
                "archetype": spec.archetype,
                "designated_card": spec.card,
                "source_pool": spec.source,
            },
            "decks": [
                {
                    **selected,
                    "cards": cards,
                    "sampling_weight": 1.0,
                }
            ],
        }
        _atomic_json(output, deck_payload)
        entries.append(
            {
                "archetype": spec.archetype,
                "designated_card": spec.card,
                "source_pool": spec.source,
                "source_deck": str(selected.get("name", "")),
                "signature": sorted(cards),
                "deck_pool": str(output),
                "deck_pool_sha256": _sha256(output),
            }
        )

    manifest = {
        "schema": "clasher-win-condition-utilization-matrix-v1",
        "validation_pool": str(validation_path),
        "validation_pool_sha256": _sha256(validation_path),
        "heldout_pool": str(heldout_path),
        "heldout_pool_sha256": _sha256(heldout_path),
        "entries": entries,
    }
    _atomic_json(manifest_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--heldout", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    payload = build_matrix(
        validation_path=args.validation,
        heldout_path=args.heldout,
        output_dir=args.output_dir,
    )
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
