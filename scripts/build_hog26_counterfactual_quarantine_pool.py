"""Build a fresh deck pool disjoint from completed held-out gameplay draws."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_pool(
    *,
    source_pools: list[Path],
    gameplay_roots: list[Path],
) -> dict[str, Any]:
    if not source_pools or not gameplay_roots:
        raise ValueError("source pools and gameplay roots are required")
    by_signature: dict[tuple[str, ...], dict[str, Any]] = {}
    for path in source_pools:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("decks", []):
            cards = tuple(sorted(str(card) for card in row.get("cards", [])))
            if len(cards) != 8:
                raise ValueError(f"source deck in {path} does not have eight cards")
            previous = by_signature.setdefault(cards, dict(row))
            if previous.get("archetype") != row.get("archetype"):
                raise ValueError("one source deck belongs to multiple archetypes")
    used: set[tuple[str, ...]] = set()
    gameplay_reports: list[Path] = []
    for root in gameplay_roots:
        for path in sorted(root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if "games" not in payload:
                continue
            gameplay_reports.append(path)
            for game in payload["games"]:
                cards = tuple(sorted(str(card) for card in game["opponent_deck"]))
                if len(cards) != 8:
                    raise ValueError(f"gameplay deck in {path} is malformed")
                used.add(cards)
    remaining = [
        row for signature, row in by_signature.items() if signature not in used
    ]
    counts = Counter(str(row.get("archetype", "")) for row in remaining)
    if not counts or "" in counts or min(counts.values()) < 1:
        raise ValueError("fresh quarantine pool lost an archetype")
    archetype_probability = 1.0 / len(counts)
    output_decks = []
    for row in remaining:
        normalized = dict(row)
        archetype = str(normalized["archetype"])
        normalized["sampling_weight"] = archetype_probability / counts[archetype]
        output_decks.append(normalized)
    output_decks.sort(
        key=lambda row: (
            str(row["archetype"]),
            str(row.get("name", "")),
            tuple(str(card) for card in row["cards"]),
        )
    )
    weight_sums: defaultdict[str, float] = defaultdict(float)
    for row in output_decks:
        weight_sums[str(row["archetype"])] += float(row["sampling_weight"])
    if any(abs(value - archetype_probability) > 1e-12 for value in weight_sums.values()):
        raise ValueError("fresh quarantine archetype weights are not balanced")
    return {
        "schema": "clasher.hog26_counterfactual_quarantine_pool.v1",
        "decks": output_decks,
        "deck_count": len(output_decks),
        "archetype_deck_counts": dict(sorted(counts.items())),
        "archetype_weight_sums": dict(sorted(weight_sums.items())),
        "excluded_gameplay_decks": len(used),
        "exact_overlap_with_gameplay": 0,
        "source_pool_sha256": {str(path): _sha256(path) for path in source_pools},
        "gameplay_report_sha256": {
            str(path): _sha256(path) for path in gameplay_reports
        },
        "promotion_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pool", type=Path, action="append", required=True)
    parser.add_argument("--gameplay-root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_pool(
        source_pools=args.source_pool,
        gameplay_roots=args.gameplay_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
