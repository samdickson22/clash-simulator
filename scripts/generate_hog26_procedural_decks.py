#!/usr/bin/env python3
"""Generate split-safe supported-card deck families for Hog outcome training."""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import random
import tempfile
from pathlib import Path
from typing import Any

from clasher.data import CardDataLoader

SCHEMA = "clasher.hog26.procedural-deck-families.v1"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_pressure_card(definition: Any) -> bool:
    return bool(
        "anti-building" in definition.tags
        or any(
            type(mechanic).__name__ == "UndergroundDeployment"
            for mechanic in definition.mechanics
        )
        or (
            definition.building_stats is not None
            and definition.building_stats.range_tiles >= 8.0
        )
    )


def _valid_deck(cards: tuple[str, ...], definitions: dict[str, Any]) -> bool:
    rows = [definitions[name] for name in cards]
    kinds = [row.kind for row in rows]
    average_elixir = sum(float(row.elixir) for row in rows) / len(rows)
    return bool(
        len(set(cards)) == 8
        and 1 <= kinds.count("spell") <= 3
        and kinds.count("troop") >= 3
        and kinds.count("building") <= 2
        and 2.5 <= average_elixir <= 4.75
        and any(_is_pressure_card(row) for row in rows)
        and any("anti-air" in row.tags for row in rows)
    )


def _covering_variants(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    definitions: dict[str, Any],
    existing: set[tuple[str, ...]],
    variants_per_family: int,
    rng: random.Random,
) -> list[tuple[str, ...]] | None:
    candidates: list[tuple[str, ...]] = []
    for left_half, right_half in itertools.product(
        itertools.combinations(left["cards"], 4),
        itertools.combinations(right["cards"], 4),
    ):
        key = tuple(sorted(set(left_half + right_half)))
        if (
            len(key) == 8
            and key not in existing
            and key not in candidates
            and _valid_deck(key, definitions)
        ):
            candidates.append(key)
    rng.shuffle(candidates)
    target = set(left["cards"]) | set(right["cards"])
    chosen: list[tuple[str, ...]] = []
    uncovered = set(target)
    for _index in range(variants_per_family):
        remaining = [candidate for candidate in candidates if candidate not in chosen]
        if not remaining:
            return None
        candidate = max(remaining, key=lambda value: len(uncovered & set(value)))
        chosen.append(candidate)
        uncovered.difference_update(candidate)
    return chosen if not uncovered else None


def _perfect_matching(
    parent_indices: set[int],
    candidates: dict[tuple[int, int], list[tuple[str, ...]]],
) -> list[tuple[tuple[int, int], list[tuple[str, ...]]]] | None:
    if not parent_indices:
        return []
    left = min(
        parent_indices,
        key=lambda index: sum(
            (min(index, other), max(index, other)) in candidates
            for other in parent_indices
            if other != index
        ),
    )
    for right in sorted(parent_indices - {left}):
        pair = (min(left, right), max(left, right))
        variants = candidates.get(pair)
        if variants is None:
            continue
        tail = _perfect_matching(parent_indices - {left, right}, candidates)
        if tail is not None:
            return [(pair, variants), *tail]
    return None


def _greedy_training_parents(
    parents: list[dict[str, Any]], *, parent_count: int, rng: random.Random
) -> set[int]:
    universe = {card for parent in parents for card in parent["cards"]}
    uncovered = set(universe)
    chosen: list[int] = []
    while uncovered and len(chosen) < parent_count:
        remaining = [index for index in range(len(parents)) if index not in chosen]
        rng.shuffle(remaining)
        selected = max(
            remaining,
            key=lambda index: len(uncovered & set(parents[index]["cards"])),
        )
        chosen.append(selected)
        uncovered.difference_update(parents[selected]["cards"])
    if uncovered:
        raise RuntimeError("training parent budget cannot cover the supported card pool")
    remaining = [index for index in range(len(parents)) if index not in chosen]
    rng.shuffle(remaining)
    chosen.extend(remaining[: parent_count - len(chosen)])
    return set(chosen)


def generate(
    source_path: Path,
    *,
    seed: int,
    train_families: int,
    development_families: int,
    holdout_families: int,
    variants_per_family: int,
    learner_deck_name: str,
    reserved_decks: tuple[str, ...],
) -> dict[str, Any]:
    source = json.loads(source_path.read_text())
    learner_rows = [
        row for row in source["decks"] if row["name"] == learner_deck_name
    ]
    if len(learner_rows) != 1:
        raise ValueError("source must contain exactly one learner deck")
    parents = [
        row for row in source["decks"] if row["name"] not in set(reserved_decks)
    ]
    family_count = train_families + development_families + holdout_families
    if min(family_count, variants_per_family) < 1:
        raise ValueError("procedural family counts must be positive")
    if family_count * variants_per_family > 256:
        raise ValueError("procedural deck manifest exceeds compiler bound")
    definitions = CardDataLoader().load_card_definitions()
    existing = {tuple(sorted(row["cards"])) for row in source["decks"]}
    seen = set(existing)
    rng = random.Random(seed)
    if len(parents) != family_count * 2:
        raise ValueError("every eligible parent must belong to exactly one family")
    pair_candidates: dict[tuple[int, int], list[tuple[str, ...]]] = {}
    for left_index, right_index in itertools.combinations(range(len(parents)), 2):
        variants = _covering_variants(
            parents[left_index],
            parents[right_index],
            definitions=definitions,
            existing=existing,
            variants_per_family=variants_per_family,
            rng=rng,
        )
        if variants is not None:
            pair_candidates[(left_index, right_index)] = variants
    train_parent_indices = _greedy_training_parents(
        parents, parent_count=train_families * 2, rng=rng
    )
    train_matches = _perfect_matching(train_parent_indices, pair_candidates)
    remaining_matches = _perfect_matching(
        set(range(len(parents))) - train_parent_indices, pair_candidates
    )
    if train_matches is None or remaining_matches is None:
        raise RuntimeError("cannot construct split-safe covering family matching")
    best_development: tuple[tuple[int, ...], tuple[int, int, int]] | None = None
    remaining_indices = range(len(remaining_matches))
    for development_indices in itertools.combinations(
        remaining_indices, development_families
    ):
        development_set = set(development_indices)
        development_cards = {
            card
            for index in development_set
            for parent_index in remaining_matches[index][0]
            for card in parents[parent_index]["cards"]
        }
        holdout_cards = {
            card
            for index in remaining_indices
            if index not in development_set
            for parent_index in remaining_matches[index][0]
            for card in parents[parent_index]["cards"]
        }
        score = (
            min(len(development_cards), len(holdout_cards)),
            len(development_cards) + len(holdout_cards),
            len(development_cards),
        )
        if best_development is None or score > best_development[1]:
            best_development = (development_indices, score)
    if best_development is None:
        raise RuntimeError("cannot assign development and holdout families")
    selected_development_indices = set(best_development[0])
    families = [
        (pair, variants, "train") for pair, variants in train_matches
    ] + [
        (
            pair,
            variants,
            "development" if index in selected_development_indices else "holdout",
        )
        for index, (pair, variants) in enumerate(remaining_matches)
    ]
    split_limits = (
        ("train", train_families),
        ("development", development_families),
        ("holdout", holdout_families),
    )
    generated_decks: list[dict[str, Any]] = []
    for family_index, ((left_index, right_index), variants, split) in enumerate(
        families
    ):
        left = parents[left_index]
        right = parents[right_index]
        family_id = f"family-{family_index:03d}"
        for variant_index, cards in enumerate(variants):
            if cards in seen:
                raise RuntimeError("generated deck collision across families")
            seen.add(cards)
            shuffled_cards = list(cards)
            rng.shuffle(shuffled_cards)
            rows = [definitions[name] for name in shuffled_cards]
            generated_decks.append(
                {
                    "name": f"Procedural {split} {family_index:03d}-{variant_index}",
                    "cards": shuffled_cards,
                    "split": split,
                    "family_id": family_id,
                    "parent_decks": [left["name"], right["name"]],
                    "average_elixir": sum(float(row.elixir) for row in rows) / 8.0,
                    "kind_counts": {
                        kind: sum(row.kind == kind for row in rows)
                        for kind in ("troop", "building", "spell")
                    },
                }
            )
    cards_by_split = {
        split: sorted(
            {
                card
                for deck in generated_decks
                if deck["split"] == split
                for card in deck["cards"]
            }
        )
        for split, _count in split_limits
    }
    learner_deck = copy.deepcopy(learner_rows[0])
    learner_deck["split"] = "learner"
    learner_deck["role"] = "fixed-policy-deck"
    decks = [learner_deck, *generated_decks]
    return {
        "schema": SCHEMA,
        "seed": seed,
        "source": {
            "path": str(source_path),
            "sha256": file_sha256(source_path),
        },
        "reserved_decks": list(reserved_decks),
        "learner_deck_name": learner_deck_name,
        "generation_contract": {
            "parents_per_family": 2,
            "each_parent_used_once": True,
            "cards_per_parent": 4,
            "variants_per_family": variants_per_family,
            "family_variants_cover_all_parent_cards": True,
            "training_parents_cover_all_eligible_cards": True,
            "whole_family_single_split": True,
            "constraints": {
                "spells": [1, 3],
                "minimum_troops": 3,
                "maximum_buildings": 2,
                "average_elixir": [2.5, 4.75],
                "pressure_card": "serialized anti-building, underground, or range>=8 building",
                "anti_air_card_required": True,
                "exact_existing_decks_forbidden": True,
            },
        },
        "counts": {
            "families": family_count,
            "decks": len(decks),
            "opponent_decks": len(generated_decks),
            "train_families": train_families,
            "development_families": development_families,
            "holdout_families": holdout_families,
            "train_decks": train_families * variants_per_family,
            "development_decks": development_families * variants_per_family,
            "holdout_decks": holdout_families * variants_per_family,
        },
        "cards_by_split": cards_by_split,
        "decks": decks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1278401)
    parser.add_argument("--train-families", type=int, default=8)
    parser.add_argument("--development-families", type=int, default=4)
    parser.add_argument("--holdout-families", type=int, default=4)
    parser.add_argument("--variants-per-family", type=int, default=4)
    parser.add_argument("--learner-deck", default="Hog 2.6 Cycle")
    parser.add_argument(
        "--reserved-deck", action="append", default=["RHogs AQ 2.9 Cycle"]
    )
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite procedural deck manifest")
    payload = generate(
        args.source,
        seed=args.seed,
        train_families=args.train_families,
        development_families=args.development_families,
        holdout_families=args.holdout_families,
        variants_per_family=args.variants_per_family,
        learner_deck_name=args.learner_deck,
        reserved_decks=tuple(args.reserved_deck),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=args.output.parent, prefix=f".{args.output.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write((json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())
        stream.flush()
    temporary.replace(args.output)
    print(json.dumps(payload["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
