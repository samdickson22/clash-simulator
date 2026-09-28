# mypy: disable-error-code="import-untyped"
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from clasher.rl.oracle_corpus import atomic_write_json, file_sha256


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return payload


def _decks(payload: dict[str, Any], *, source: Path) -> list[dict[str, Any]]:
    rows = payload.get("decks")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{source} has no deck rows")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{source} contains a non-object deck row")
    return rows


def _signature(deck: dict[str, Any]) -> tuple[str, ...]:
    cards = deck.get("cards")
    if not isinstance(cards, list) or len(cards) != 8:
        raise ValueError("every deck must contain exactly eight cards")
    names = tuple(str(card) for card in cards)
    if len(set(names)) != len(names):
        raise ValueError("a deck cannot contain duplicate cards")
    return tuple(sorted(names))


def _slug(value: str) -> str:
    return value.replace("-", "_")


def build_pools(
    *,
    source_pool: Path,
    validation_pool: Path,
    heldout_pool: Path,
    utilization_manifest: Path,
    output_dir: Path,
    manifest_out: Path,
) -> dict[str, Any]:
    source_payload = _load_object(source_pool)
    source_decks = _decks(source_payload, source=source_pool)
    validation_decks = _decks(
        _load_object(validation_pool), source=validation_pool
    )
    heldout_decks = _decks(_load_object(heldout_pool), source=heldout_pool)
    excluded_signatures = {
        *(_signature(deck) for deck in validation_decks),
        *(_signature(deck) for deck in heldout_decks),
    }
    source_overlap = [
        deck for deck in source_decks if _signature(deck) in excluded_signatures
    ]
    if source_overlap:
        raise ValueError("source training pool overlaps a frozen evaluation deck")

    utilization = _load_object(utilization_manifest)
    entries = utilization.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("utilization manifest has no entries")
    training_specs = [entry for entry in entries if entry.get("source_pool") == "validation"]
    heldout_specs = [entry for entry in entries if entry.get("source_pool") == "heldout"]
    if not training_specs or not heldout_specs:
        raise ValueError("utilization manifest must define trainable and held-out archetypes")

    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for spec in training_specs:
        archetype = str(spec["archetype"])
        designated_card = str(spec["designated_card"])
        selected = [
            dict(deck) for deck in source_decks if deck.get("archetype") == archetype
        ]
        if not selected:
            raise ValueError(f"source training pool has no {archetype!r} decks")
        if any(designated_card not in deck["cards"] for deck in selected):
            raise ValueError(
                f"{archetype!r} training pool omitted its designated win condition"
            )
        signatures = [_signature(deck) for deck in selected]
        if len(signatures) != len(set(signatures)):
            raise ValueError(f"{archetype!r} training pool contains duplicate decks")
        weight = 1.0 / len(selected)
        for deck in selected:
            deck["sampling_weight"] = weight
        output = output_dir / f"{_slug(archetype)}.json"
        if output.exists():
            raise FileExistsError(f"refusing to overwrite {output}")
        payload = {
            "schema_version": 1,
            "decks": selected,
            "metadata": {
                "purpose": "student_state_symmetry_dagger_training_archetype",
                "archetype": archetype,
                "designated_card": designated_card,
                "source_pool": str(source_pool.resolve()),
                "source_pool_sha256": file_sha256(source_pool),
                "validation_pool_sha256": file_sha256(validation_pool),
                "heldout_pool_sha256": file_sha256(heldout_pool),
                "frozen_evaluation_signature_overlap": 0,
            },
        }
        atomic_write_json(output, payload)
        records.append(
            {
                "archetype": archetype,
                "designated_card": designated_card,
                "decks": len(selected),
                "output": str(output.resolve()),
                "output_sha256": file_sha256(output),
            }
        )

    heldout_archetypes = sorted(str(spec["archetype"]) for spec in heldout_specs)
    source_archetypes = {str(deck.get("archetype")) for deck in source_decks}
    accidental_heldout = sorted(source_archetypes.intersection(heldout_archetypes))
    if accidental_heldout:
        raise ValueError(
            f"source pool contains held-out archetypes: {accidental_heldout}"
        )
    manifest = {
        "schema_version": 1,
        "source_pool": str(source_pool.resolve()),
        "source_pool_sha256": file_sha256(source_pool),
        "validation_pool": str(validation_pool.resolve()),
        "validation_pool_sha256": file_sha256(validation_pool),
        "heldout_pool": str(heldout_pool.resolve()),
        "heldout_pool_sha256": file_sha256(heldout_pool),
        "utilization_manifest": str(utilization_manifest.resolve()),
        "utilization_manifest_sha256": file_sha256(utilization_manifest),
        "frozen_evaluation_signature_overlap": 0,
        "heldout_archetypes": heldout_archetypes,
        "heldout_archetypes_in_source": accidental_heldout,
        "training_archetypes": records,
    }
    serialized = json.dumps(manifest, sort_keys=True).encode()
    manifest["content_sha256"] = hashlib.sha256(serialized).hexdigest()
    atomic_write_json(manifest_out, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-pool", required=True, type=Path)
    parser.add_argument("--validation-pool", required=True, type=Path)
    parser.add_argument("--heldout-pool", required=True, type=Path)
    parser.add_argument("--utilization-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest-out", required=True, type=Path)
    args = parser.parse_args()
    for path in (
        args.source_pool,
        args.validation_pool,
        args.heldout_pool,
        args.utilization_manifest,
    ):
        if not path.is_file():
            raise SystemExit(f"missing required input: {path}")
    if args.manifest_out.exists():
        raise SystemExit("refusing to overwrite archetype-pool manifest")
    result = build_pools(
        source_pool=args.source_pool,
        validation_pool=args.validation_pool,
        heldout_pool=args.heldout_pool,
        utilization_manifest=args.utilization_manifest,
        output_dir=args.output_dir,
        manifest_out=args.manifest_out,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
