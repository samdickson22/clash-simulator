"""Generate deterministic semantic deck variants and held-out archetype splits."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.deck_curriculum import (
    HELD_OUT_ARCHETYPES,
    CurriculumDeck,
    generate_structured_decks,
    infer_archetype,
    split_curriculum,
)
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks


def _load_seed_decks(path: Path, *, source: str) -> list[CurriculumDeck]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = []
    for index, raw in enumerate(payload.get("decks", [])):
        cards = tuple(str(card) for card in raw.get("cards", ()))
        if len(cards) != 8 or len(set(cards)) != 8:
            continue
        name = str(raw.get("name") or f"{source} deck {index + 1}")
        result.append(
            CurriculumDeck(
                name=name,
                cards=cards,
                archetype=str(raw.get("archetype") or infer_archetype(cards)),
                source=str(raw.get("source") or source),
            )
        )
    return result


def _write_decks(
    path: Path,
    decks: list[CurriculumDeck],
    *,
    metadata: dict[str, Any],
) -> str:
    archetype_counts = Counter(deck.archetype for deck in decks)
    payload = {
        "schema_version": 1,
        "metadata": metadata,
        "decks": [
            {
                **deck.as_json(),
                "sampling_weight": 1.0 / archetype_counts[deck.archetype],
            }
            for deck in decks
        ],
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-decks", default="decks.json")
    parser.add_argument("--real-decks")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--variants-per-seed", type=int, default=16)
    parser.add_argument("--neighbor-pool", type=int, default=8)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=1040001)
    parser.add_argument(
        "--held-out-archetype",
        action="append",
        default=[],
        help="repeat to replace the default whole-archetype holdout set",
    )
    args = parser.parse_args()

    base_path = resolve_decks_path(args.base_decks, must_exist=True)
    seed_decks = _load_seed_decks(base_path, source="project-base")
    if args.real_decks:
        real_path = resolve_path(args.real_decks, must_exist=True)
        seed_decks.extend(_load_seed_decks(real_path, source="real-public"))
    card_pool = unique_cards_from_decks(load_deck_pool(base_path))
    generated = generate_structured_decks(
        seed_decks,
        card_pool=card_pool,
        variants_per_seed=args.variants_per_seed,
        seed=args.seed,
        neighbor_pool=args.neighbor_pool,
    )
    held_out_archetypes = frozenset(args.held_out_archetype) or HELD_OUT_ARCHETYPES
    train, validation, held_out = split_curriculum(
        generated,
        validation_fraction=args.validation_fraction,
        seed=args.seed + 1,
        held_out_archetypes=held_out_archetypes,
    )
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    common_metadata = {
        "base_decks": str(base_path),
        "real_decks": args.real_decks,
        "seed": args.seed,
        "variants_per_seed": args.variants_per_seed,
        "neighbor_pool": args.neighbor_pool,
        "held_out_archetypes": sorted(held_out_archetypes),
        "card_count": len(card_pool),
    }
    outputs = {}
    for label, decks in (
        ("all", generated),
        ("train", train),
        ("validation", validation),
        ("heldout", held_out),
    ):
        filename = output_dir / f"{label}.json"
        outputs[label] = {
            "path": str(filename),
            "decks": len(decks),
            "sha256": _write_decks(
                filename,
                decks,
                metadata={**common_metadata, "split": label},
            ),
            "archetypes": dict(sorted(Counter(d.archetype for d in decks).items())),
        }
    report = {
        "schema_version": 1,
        "seed_decks": len(seed_decks),
        "unique_generated_decks": len(generated),
        "outputs": outputs,
    }
    report_path = output_dir / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
