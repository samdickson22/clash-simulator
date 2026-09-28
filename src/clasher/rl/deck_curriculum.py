from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from clasher.data import CardDataLoader

from .card_semantics import (
    CardSemanticProfile,
    semantic_card_profile,
    semantic_distance,
)

HELD_OUT_ARCHETYPES = frozenset(
    {
        "graveyard",
        "lava-hound",
        "royal-hogs",
        "x-bow",
    }
)


@dataclass(frozen=True)
class CurriculumDeck:
    name: str
    cards: tuple[str, ...]
    archetype: str
    source: str
    parent: str | None = None
    substitutions: int = 0

    def as_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cards": list(self.cards),
            "archetype": self.archetype,
            "source": self.source,
            "parent": self.parent,
            "substitutions": self.substitutions,
        }


def infer_archetype(cards: Sequence[str]) -> str:
    card_set = set(cards)
    priorities = (
        ("x-bow", {"Xbow"}),
        ("graveyard", {"Graveyard"}),
        ("lava-hound", {"LavaHound"}),
        ("royal-hogs", {"RoyalHogs"}),
        ("golem", {"Golem"}),
        ("giant", {"Giant"}),
        ("hog", {"HogRider"}),
        ("balloon", {"Balloon"}),
        ("log-bait", {"GoblinBarrel"}),
        ("bridge-spam", {"BattleRam"}),
        ("wall-breakers", {"Wallbreakers"}),
        ("miner", {"Miner"}),
        ("skeleton-barrel", {"SkeletonBarrel"}),
        ("mega-knight", {"MegaKnight"}),
    )
    for archetype, required in priorities:
        if required <= card_set:
            return archetype
    return "control"


def _profile_map(
    card_names: Sequence[str], loader: CardDataLoader
) -> dict[str, CardSemanticProfile]:
    return {
        name: semantic_card_profile(name, loader=loader)
        for name in sorted(set(card_names))
    }


def _is_valid_deck(
    cards: Sequence[str],
    profiles: dict[str, CardSemanticProfile],
) -> bool:
    if len(cards) != 8 or len(set(cards)) != 8:
        return False
    selected = [profiles[name] for name in cards]
    average_elixir = sum(profile.mana_cost for profile in selected) / 8.0
    if not 2.2 <= average_elixir <= 5.5:
        return False
    roles = [profile.role for profile in selected]
    if not any(
        role in {"building_target", "siege", "spawn_spell"} for role in roles
    ) and not ({"Miner", "Wallbreakers"} & set(cards)):
        return False
    if not any(profile.card_type == "spell" for profile in selected):
        return False
    air_defenders = sum(
        bool(profile.vector[16])
        or profile.role in {"damage_spell", "small_spell", "control_spell"}
        for profile in selected
    )
    if air_defenders < 2:
        return False
    return (
        sum(profile.card_type in {"troop", "champion"} for profile in selected) >= 3
    )


def _replacement_neighbors(
    profiles: dict[str, CardSemanticProfile],
    *,
    neighbor_pool: int,
) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for name, profile in profiles.items():
        ranked = sorted(
            (
                (semantic_distance(profile, other), other_name)
                for other_name, other in profiles.items()
                if other_name != name
                and abs(profile.mana_cost - other.mana_cost) <= 2.0
            ),
            key=lambda item: (item[0], item[1]),
        )
        result[name] = tuple(
            other_name
            for distance, other_name in ranked
            if np.isfinite(distance)
        )[:neighbor_pool]
    return result


def generate_structured_decks(
    seed_decks: Sequence[CurriculumDeck],
    *,
    card_pool: Sequence[str],
    variants_per_seed: int,
    seed: int,
    neighbor_pool: int = 8,
    max_attempts_per_seed: int = 5000,
) -> list[CurriculumDeck]:
    if variants_per_seed < 0:
        raise ValueError("variants_per_seed must be non-negative")
    if neighbor_pool <= 0:
        raise ValueError("neighbor_pool must be positive")
    loader = CardDataLoader()
    all_names = sorted(
        set(card_pool).union(*(deck.cards for deck in seed_decks))
    )
    profiles = _profile_map(all_names, loader)
    neighbors = _replacement_neighbors(profiles, neighbor_pool=neighbor_pool)
    rng = random.Random(seed)
    generated: list[CurriculumDeck] = []
    seen: set[tuple[str, ...]] = set()
    for source in seed_decks:
        canonical = tuple(sorted(source.cards))
        if canonical not in seen:
            generated.append(source)
            seen.add(canonical)
        produced = 0
        for _ in range(max_attempts_per_seed):
            if produced >= variants_per_seed:
                break
            cards = list(source.cards)
            substitution_count = rng.choices((1, 2, 3), weights=(0.55, 0.35, 0.10))[0]
            positions = rng.sample(range(8), k=substitution_count)
            changed = 0
            for position in positions:
                choices = [
                    candidate
                    for candidate in neighbors[cards[position]]
                    if candidate not in cards
                ]
                if not choices:
                    continue
                cards[position] = rng.choice(choices)
                changed += 1
            if (
                changed == 0
                or infer_archetype(cards) != source.archetype
                or not _is_valid_deck(cards, profiles)
            ):
                continue
            canonical = tuple(sorted(cards))
            if canonical in seen:
                continue
            produced += 1
            seen.add(canonical)
            generated.append(
                CurriculumDeck(
                    name=f"{source.name} semantic variant {produced:02d}",
                    cards=tuple(cards),
                    archetype=source.archetype,
                    source="semantic-procedural",
                    parent=source.name,
                    substitutions=changed,
                )
            )
    return generated


def split_curriculum(
    decks: Sequence[CurriculumDeck],
    *,
    validation_fraction: float,
    seed: int,
    held_out_archetypes: frozenset[str] = HELD_OUT_ARCHETYPES,
) -> tuple[list[CurriculumDeck], list[CurriculumDeck], list[CurriculumDeck]]:
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be between zero and one")
    held_out = [deck for deck in decks if deck.archetype in held_out_archetypes]
    eligible = [deck for deck in decks if deck.archetype not in held_out_archetypes]
    rng = random.Random(seed)
    by_archetype: dict[str, list[CurriculumDeck]] = {}
    for deck in eligible:
        by_archetype.setdefault(deck.archetype, []).append(deck)
    train: list[CurriculumDeck] = []
    validation: list[CurriculumDeck] = []
    for archetype in sorted(by_archetype):
        group = sorted(by_archetype[archetype], key=lambda deck: deck.name)
        rng.shuffle(group)
        count = max(1, round(len(group) * validation_fraction))
        validation.extend(group[:count])
        train.extend(group[count:])
    key = lambda deck: (deck.archetype, deck.name)
    return sorted(train, key=key), sorted(validation, key=key), sorted(held_out, key=key)
