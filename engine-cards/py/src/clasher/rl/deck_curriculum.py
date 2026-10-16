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
    *,
    require_win_condition: bool = True,
) -> bool:
    if len(cards) != 8 or len(set(cards)) != 8:
        return False
    selected = [profiles[name] for name in cards]
    average_elixir = sum(profile.mana_cost for profile in selected) / 8.0
    if not 2.2 <= average_elixir <= 5.5:
        return False
    roles = [profile.role for profile in selected]
    if require_win_condition and not any(
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
    # Reserve every parent before generating variants so an earlier derivative
    # cannot replace a later parent's provenance record.
    generated = list(seed_decks)
    seen = {tuple(sorted(source.cards)) for source in seed_decks}
    for source in seed_decks:
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
                or not _is_valid_deck(cards, profiles, require_win_condition=source.archetype != "control")
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
    groups = curriculum_families(decks)
    held_out: list[CurriculumDeck] = []
    by_archetype: dict[str, list[list[CurriculumDeck]]] = {}
    for group in groups:
        if any(deck.archetype in held_out_archetypes for deck in group):
            held_out.extend(group)
        else:
            by_archetype.setdefault(min(deck.archetype for deck in group), []).append(group)
    rng = random.Random(seed)
    train: list[CurriculumDeck] = []
    validation: list[CurriculumDeck] = []
    for archetype in sorted(by_archetype):
        groups_for_archetype = by_archetype[archetype]
        rng.shuffle(groups_for_archetype)
        # A lone family stays in training; splitting its variants would leak.
        count = min(len(groups_for_archetype) - 1, max(1, round(len(groups_for_archetype) * validation_fraction)))
        validation.extend(deck for group in groups_for_archetype[:count] for deck in group)
        train.extend(deck for group in groups_for_archetype[count:] for deck in group)
    key = lambda deck: (deck.archetype, deck.name)
    return sorted(train, key=key), sorted(validation, key=key), sorted(held_out, key=key)


def curriculum_families(decks: Sequence[CurriculumDeck]) -> list[list[CurriculumDeck]]:
    """Connect parents, descendants and identical rosters before assigning roles."""
    by_name = {deck.name: deck for deck in decks}
    if len(by_name) != len(decks):
        raise ValueError("curriculum names must be unique")
    roots: dict[str, str] = {}

    def root(name: str) -> str:
        roots.setdefault(name, name)
        if roots[name] != name:
            roots[name] = root(roots[name])
        return roots[name]

    def join(left: str, right: str) -> None:
        a, b = sorted((root(left), root(right)))
        roots[b] = a

    rosters: dict[tuple[str, ...], str] = {}
    for deck in sorted(decks, key=lambda item: item.name):
        root(deck.name)
        if deck.parent:
            join(deck.name, deck.parent)
        roster = tuple(sorted(deck.cards))
        if roster in rosters:
            join(deck.name, rosters[roster])
        rosters[roster] = deck.name
    groups: dict[str, list[CurriculumDeck]] = {}
    for deck in sorted(decks, key=lambda item: item.name):
        groups.setdefault(root(deck.name), []).append(deck)
    return [groups[name] for name in sorted(groups)]


def pilot_curriculum(*, seed: int = 20260928, variants_per_seed: int = 2) -> dict[str, list[dict[str, Any]]]:
    """Prepare prospective 16-card roles, without collecting games or labels.

    These are engineering rosters. Each role samples structured, neighboring
    and legal stress decks with mass 0.6, 0.3 and 0.1 respectively.
    """
    from .public_scripted_opponent import SUPPORTED_CARDS

    # These independently authored engineering roots define family identity.
    # Every generated substitution below inherits its actual root name.
    bases = (
        ("hog-cycle", ("HogRider", "Musketeer", "Cannon", "Fireball", "Log", "Skeletons", "IceGolem", "IceSpirit")),
        ("hog-knight-control", ("HogRider", "Knight", "Tesla", "Archers", "Goblins", "Zap", "Fireball", "IceSpirit")),
        ("hog-prince-pressure", ("HogRider", "Prince", "DarkPrince", "Goblins", "Zap", "Fireball", "Skeletons", "Musketeer")),
        ("hog-double-building", ("HogRider", "Cannon", "Tesla", "Knight", "Archers", "Zap", "Log", "IceGolem")),
        ("giant-double-prince", ("Giant", "Musketeer", "Prince", "DarkPrince", "Archers", "Goblins", "Zap", "Fireball")),
        ("giant-cycle", ("Giant", "Knight", "Archers", "IceSpirit", "Skeletons", "Zap", "Fireball", "Tesla")),
        ("giant-control", ("Giant", "Musketeer", "Cannon", "IceGolem", "Goblins", "Log", "Fireball", "Knight")),
        ("giant-heavy-pressure", ("Giant", "Prince", "DarkPrince", "Knight", "Archers", "Tesla", "Zap", "Log")),
        ("prince-tesla-control", ("Prince", "DarkPrince", "Knight", "Archers", "Goblins", "Tesla", "Log", "Zap")),
        ("prince-cycle", ("Prince", "Musketeer", "Cannon", "IceGolem", "Skeletons", "IceSpirit", "Zap", "Fireball")),
        ("knight-double-building", ("Knight", "Archers", "Musketeer", "Tesla", "Cannon", "Skeletons", "Log", "Fireball")),
        ("dark-prince-pressure", ("DarkPrince", "Prince", "Archers", "Musketeer", "Goblins", "IceSpirit", "Fireball", "Log")),
    )
    parents = [CurriculumDeck(f"pilot-{name}", cards, infer_archetype(cards), "engineering-structured") for name, cards in bases]
    used = {tuple(sorted(deck.cards)) for deck in parents}
    if len(used) != len(parents):
        raise ValueError("duplicate pilot parent")
    rng = random.Random(seed)
    generated = generate_structured_decks(parents, card_pool=sorted(SUPPORTED_CARDS), variants_per_seed=variants_per_seed, seed=seed)
    roles: dict[str, list[CurriculumDeck]] = {name: [] for name in ("training", "development", "acceptance")}
    by_archetype: dict[str, list[list[CurriculumDeck]]] = {}
    for group in curriculum_families(generated):
        by_archetype.setdefault(group[0].archetype, []).append(group)
    for archetype in sorted(by_archetype):
        families = by_archetype[archetype]
        rng.shuffle(families)
        for index, family in enumerate(families):
            role = "development" if index == 0 else "acceptance" if index == 1 else "training"
            roles[role].extend(family)
    used.update(tuple(sorted(deck.cards)) for deck in generated)
    for role, decks in roles.items():
        while True:
            cards = tuple(rng.sample(sorted(SUPPORTED_CARDS), 8))
            canonical = tuple(sorted(cards))
            if canonical not in used:
                used.add(canonical)
                break
        decks.append(CurriculumDeck(f"pilot-{role}-stress", cards, infer_archetype(cards), "legal-stress"))
    masses = {"engineering-structured": 0.6, "semantic-procedural": 0.3, "legal-stress": 0.1}
    result: dict[str, list[dict[str, Any]]] = {}
    for role, decks in roles.items():
        counts = {source: sum(deck.source == source for deck in decks) for source in masses}
        if not all(counts.values()):
            raise ValueError("every pilot role requires structured, neighbor and stress decks")
        result[role] = [deck.as_json() | {"role": role, "sampling_weight": masses[deck.source] / counts[deck.source]} for deck in sorted(decks, key=lambda item: item.name)]
    return result
