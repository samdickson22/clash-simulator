"""Build signature-disjoint deck splits while exposing every enabled card in train."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any


def signature(row: dict[str, Any]) -> tuple[str, ...]:
    cards = tuple(sorted(str(card) for card in row.get("cards", ())))
    if len(cards) != 8 or len(set(cards)) != 8:
        raise ValueError("every deck must contain eight unique cards")
    return cards


def _validate_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("source deck pool is empty")
    signatures: set[tuple[str, ...]] = set()
    for row in rows:
        deck_signature = signature(row)
        if deck_signature in signatures:
            raise ValueError("source deck pool contains duplicate signatures")
        signatures.add(deck_signature)
        if not str(row.get("archetype", "")):
            raise ValueError("every deck must identify an archetype")


def build_card_complete_splits(
    payload: dict[str, Any],
    *,
    validation_fraction: float,
    heldout_fraction: float,
    seed: int,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if validation_fraction <= 0.0 or heldout_fraction <= 0.0:
        raise ValueError("split fractions must be positive")
    if validation_fraction + heldout_fraction >= 1.0:
        raise ValueError("validation and heldout fractions leave no training data")
    rows = payload.get("decks")
    if not isinstance(rows, list):
        raise TypeError("source deck pool has no decks")
    _validate_rows(rows)

    rng = random.Random(seed)
    by_archetype: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_archetype.setdefault(str(row["archetype"]), []).append(row)
    splits: dict[str, list[dict[str, Any]]] = {
        "train": [],
        "validation": [],
        "heldout": [],
    }
    for archetype in sorted(by_archetype):
        group = sorted(by_archetype[archetype], key=lambda row: str(row["name"]))
        rng.shuffle(group)
        validation_count = max(1, round(len(group) * validation_fraction))
        heldout_count = max(1, round(len(group) * heldout_fraction))
        if validation_count + heldout_count >= len(group):
            raise ValueError(f"archetype {archetype!r} is too small for three splits")
        splits["validation"].extend(group[:validation_count])
        splits["heldout"].extend(
            group[validation_count : validation_count + heldout_count]
        )
        splits["train"].extend(group[validation_count + heldout_count :])

    all_cards = set().union(*(set(signature(row)) for row in rows))
    train_cards = set().union(*(set(signature(row)) for row in splits["train"]))
    moved_for_coverage: list[dict[str, Any]] = []
    while missing := all_cards - train_cards:
        candidates = [
            (source, index, row)
            for source in ("heldout", "validation")
            for index, row in enumerate(splits[source])
            if set(signature(row)) & missing
        ]
        if not candidates:
            raise ValueError(f"cannot repair training card coverage: {sorted(missing)}")
        source, index, row = max(
            candidates,
            key=lambda item: (
                len(set(signature(item[2])) & missing),
                item[0] == "validation",
                str(item[2]["archetype"]),
                str(item[2]["name"]),
            ),
        )
        splits[source].pop(index)
        splits["train"].append(row)
        train_cards.update(signature(row))
        moved_for_coverage.append(
            {
                "from": source,
                "name": str(row["name"]),
                "archetype": str(row["archetype"]),
                "cards_added": sorted(set(signature(row)) & missing),
            }
        )

    for split_rows in splits.values():
        split_rows.sort(
            key=lambda row: (str(row["archetype"]), str(row["name"]))
        )
    signature_sets = {
        name: {signature(row) for row in split_rows}
        for name, split_rows in splits.items()
    }
    overlaps = {
        f"{left}_{right}": len(signature_sets[left] & signature_sets[right])
        for left, right in (
            ("train", "validation"),
            ("train", "heldout"),
            ("validation", "heldout"),
        )
    }
    if any(overlaps.values()):
        raise AssertionError("deck split signatures overlap")
    if train_cards != all_cards:
        raise AssertionError("training split does not cover every source card")
    for archetype in by_archetype:
        if not any(row["archetype"] == archetype for row in splits["train"]):
            raise AssertionError(f"training split lost archetype {archetype!r}")
        if not any(row["archetype"] == archetype for row in splits["heldout"]):
            raise AssertionError(f"heldout split lost archetype {archetype!r}")

    report = {
        "schema_version": 1,
        "method": "card-complete-signature-disjoint-archetype-stratified-v1",
        "seed": seed,
        "validation_fraction": validation_fraction,
        "heldout_fraction": heldout_fraction,
        "source_decks": len(rows),
        "source_cards": len(all_cards),
        "training_card_coverage": len(train_cards),
        "training_card_coverage_rate": len(train_cards) / len(all_cards),
        "exact_signature_overlaps": overlaps,
        "moved_for_card_coverage": moved_for_coverage,
        "splits": {
            name: {
                "decks": len(split_rows),
                "archetypes": dict(
                    sorted(Counter(str(row["archetype"]) for row in split_rows).items())
                ),
                "unique_cards": len(
                    set().union(*(set(signature(row)) for row in split_rows))
                ),
            }
            for name, split_rows in splits.items()
        },
        "whole_archetype_zero_shot": False,
        "heldout_definition": (
            "unseen exact deck signatures in every archetype; every source card "
            "is represented in training"
        ),
    }
    return splits, report


def _encoded_pool(
    rows: list[dict[str, Any]],
    *,
    metadata: dict[str, Any],
) -> bytes:
    counts = Counter(str(row["archetype"]) for row in rows)
    payload = {
        "schema_version": 1,
        "metadata": metadata,
        "decks": [
            {**row, "sampling_weight": 1.0 / counts[str(row["archetype"])]}
            for row in rows
        ],
    }
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    parser.add_argument("--heldout-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=1057201)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit("refusing to overwrite deck split output directory")
    payload = json.loads(args.source.read_text())
    splits, report = build_card_complete_splits(
        payload,
        validation_fraction=args.validation_fraction,
        heldout_fraction=args.heldout_fraction,
        seed=args.seed,
    )
    args.output_dir.mkdir(parents=True)
    source_sha = hashlib.sha256(args.source.read_bytes()).hexdigest()
    for name, rows in splits.items():
        path = args.output_dir / f"{name}.json"
        path.write_bytes(
            _encoded_pool(
                rows,
                metadata={
                    "split": name,
                    "source": str(args.source.resolve()),
                    "source_sha256": source_sha,
                    "method": report["method"],
                    "seed": args.seed,
                },
            )
        )
        report["splits"][name].update(
            {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    report.update(
        {
            "source": str(args.source.resolve()),
            "source_sha256": source_sha,
        }
    )
    report_path = args.output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
