"""Filter a weighted deck-pool artifact by required card membership."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--card", action="append", required=True)
    parser.add_argument("--match", choices=("any", "all"), default="any")
    args = parser.parse_args()
    requested = set(args.card)
    payload: dict[str, Any] = json.loads(args.source.read_text())
    selected: list[dict[str, Any]] = []
    for row in payload.get("decks", []):
        cards = {str(card) for card in row.get("cards", [])}
        keep = (
            bool(cards.intersection(requested))
            if args.match == "any"
            else requested <= cards
        )
        if keep:
            selected.append(dict(row))
    if not selected:
        raise ValueError("deck filter selected no decks")
    archetype_counts = Counter(str(row.get("archetype", "unknown")) for row in selected)
    for row in selected:
        archetype = str(row.get("archetype", "unknown"))
        row["sampling_weight"] = 1.0 / archetype_counts[archetype]
    output = {
        "schema_version": 1,
        "metadata": {
            "source": str(args.source.resolve()),
            "cards": sorted(requested),
            "match": args.match,
        },
        "decks": selected,
    }
    encoded = (json.dumps(output, indent=2, sort_keys=True) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    counts = {
        card: sum(card in row.get("cards", []) for row in selected)
        for card in sorted(requested)
    }
    report = {
        "schema_version": 1,
        "source": str(args.source.resolve()),
        "output": str(args.output.resolve()),
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "match": args.match,
        "requested_cards": sorted(requested),
        "selected_decks": len(selected),
        "card_counts": counts,
        "archetype_counts": dict(sorted(archetype_counts.items())),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
