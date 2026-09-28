"""Build a deck pool with exact held-out deck signatures removed."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _signature(row: dict[str, Any]) -> tuple[str, ...]:
    cards = tuple(sorted(str(card) for card in row.get("cards", ())))
    if len(cards) != 8 or len(set(cards)) != 8:
        raise ValueError("every deck must contain exactly eight unique cards")
    return cards


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exclude_deck_signatures(
    source_payload: dict[str, Any],
    exclusion_payloads: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_rows = source_payload.get("decks")
    if not isinstance(source_rows, list) or not source_rows:
        raise ValueError("source deck pool must contain decks")
    exclusion_signatures: set[tuple[str, ...]] = set()
    for payload in exclusion_payloads:
        rows = payload.get("decks")
        if not isinstance(rows, list) or not rows:
            raise ValueError("every exclusion pool must contain decks")
        exclusion_signatures.update(_signature(row) for row in rows)

    source_signatures: set[tuple[str, ...]] = set()
    original_weight_by_archetype: dict[str, float] = defaultdict(float)
    retained_weight_by_archetype: dict[str, float] = defaultdict(float)
    retained: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for raw_row in source_rows:
        if not isinstance(raw_row, dict):
            raise TypeError("deck rows must be JSON objects")
        row = dict(raw_row)
        signature = _signature(row)
        if signature in source_signatures:
            raise ValueError("source deck pool contains a duplicate signature")
        source_signatures.add(signature)
        archetype = str(row.get("archetype", ""))
        if not archetype:
            raise ValueError("source decks must identify an archetype")
        weight = float(row.get("sampling_weight", 1.0))
        if weight <= 0.0:
            raise ValueError("source deck weights must be positive")
        original_weight_by_archetype[archetype] += weight
        if signature in exclusion_signatures:
            excluded.append(row)
        else:
            retained.append(row)
            retained_weight_by_archetype[archetype] += weight

    if not retained or not excluded:
        raise ValueError("signature exclusion must retain and exclude at least one deck")
    emptied = sorted(
        archetype
        for archetype in original_weight_by_archetype
        if retained_weight_by_archetype[archetype] <= 0.0
    )
    if emptied:
        raise ValueError(f"signature exclusion emptied archetypes: {emptied}")

    for row in retained:
        archetype = str(row["archetype"])
        row["sampling_weight"] = float(row.get("sampling_weight", 1.0)) * (
            original_weight_by_archetype[archetype]
            / retained_weight_by_archetype[archetype]
        )
    retained_signatures = {_signature(row) for row in retained}
    overlap = retained_signatures & exclusion_signatures
    if overlap:
        raise AssertionError("held-out deck signatures survived filtering")

    output = {
        **source_payload,
        "decks": retained,
        "metadata": {
            **dict(source_payload.get("metadata", {})),
            "exact_signature_exclusion": True,
            "source_decks": len(source_rows),
            "retained_decks": len(retained),
            "excluded_decks": len(excluded),
        },
    }
    manifest = {
        "schema_version": 1,
        "source_decks": len(source_rows),
        "retained_decks": len(retained),
        "excluded_decks": len(excluded),
        "excluded_names": sorted(str(row.get("name", "")) for row in excluded),
        "excluded_signatures": [list(_signature(row)) for row in excluded],
        "retained_exclusion_overlap": len(overlap),
        "archetype_weight_before": dict(sorted(original_weight_by_archetype.items())),
        "archetype_weight_after": {
            archetype: sum(
                float(row["sampling_weight"])
                for row in retained
                if row["archetype"] == archetype
            )
            for archetype in sorted(original_weight_by_archetype)
        },
    }
    return output, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--exclude", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest-out", required=True, type=Path)
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8"))
    exclusions = [
        json.loads(path.read_text(encoding="utf-8")) for path in args.exclude
    ]
    output, manifest = exclude_deck_signatures(source, exclusions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest.update(
        {
            "source": str(args.source.resolve()),
            "source_sha256": _sha256(args.source),
            "exclusions": [str(path.resolve()) for path in args.exclude],
            "exclusion_sha256": [_sha256(path) for path in args.exclude],
            "output": str(args.output.resolve()),
            "output_sha256": _sha256(args.output),
        }
    )
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
