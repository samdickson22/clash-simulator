"""C56 prospective root declarations from a pinned human training-deck catalog.

These declarations do not admit cards or launch capture. Legacy v2 admissions
remain separate. A failed/missing episode is retained, never replaced.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Iterable
from types import MappingProxyType
from typing import Literal

import numpy as np
from pydantic import Field, model_validator

from clasher.unit_traits import is_air_unit_card

from .c56_scripted import C56_ADDED_CARDS
from .public_action_mask import PublicActionMaskInput
from .public_observation import ConfidenceAwareActorObservation
from .public_scripted_opponent import SUPPORTED_CARDS, PublicScriptedOpponent
from .readiness_execution import canonical_sha
from .readiness_root_bank import (
    Context,
    RootRequest,
    RootSelection,
    context_matches,
    select_root,
)
from .training_readiness_v2 import CONDITIONS, SHA, Record

BUNDLES = MappingProxyType(
    {
        "B1": (
            "BarbLog",
            "Arrows",
            "Tornado",
            "ElectroSpirit",
            "Lightning",
            "Poison",
            "Rocket",
            "Earthquake",
            "RoyalDelivery",
        ),
        "B2": (
            "BabyDragon",
            "Minions",
            "Bats",
            "MinionHorde",
            "Balloon",
            "Wizard",
            "Valkyrie",
            "Princess",
            "Firecracker",
            "BlowdartGoblin",
        ),
        "B3": (
            "AngryBarbarians",
            "Berserker",
            "MiniPekka",
            "SkeletonArmy",
            "GoblinGang",
            "Rascals",
            "Golem",
            "RoyalHogs",
            "Wallbreakers",
            "FireSpirits",
            "Ghost",
        ),
        "B4": (
            "FirespiritHut",
            "GoblinHut",
            "InfernoTower",
            "Xbow",
            "BombTower",
            "Miner",
            "GoblinBarrel",
            "MightyMiner",
            "Goblinstein",
            "ArcherQueen",
        ),
    }
)
C56_SCOPE = tuple(sorted(SUPPORTED_CARDS | C56_ADDED_CARDS))
Bundle = Literal["B1", "B2", "B3", "B4"]
MechanicContext = (
    Context
    | Literal["air_threat", "building_pull", "spell_value", "enemy_side_deployment"]
)
AIR_CARDS = frozenset({"BabyDragon", "Minions", "Bats", "MinionHorde", "Balloon"})


def archetype(cards: tuple[str, ...]) -> str:
    for label, key in (
        ("x-bow siege", "Xbow"),
        ("golem beatdown", "Golem"),
        ("royal hogs", "RoyalHogs"),
        ("hog cycle", "HogRider"),
        ("balloon", "Balloon"),
        ("log bait", "GoblinBarrel"),
        ("miner control", "Miner"),
        ("giant beatdown", "Giant"),
    ):
        if key in cards:
            return label
    return "ground pressure"


class HumanDeckFrequency(Record):
    cards: tuple[str, ...]
    frequency: int = Field(ge=1)

    @model_validator(mode="after")
    def deck(self):
        if (
            len(self.cards) != 8
            or len(set(self.cards)) != 8
            or not set(self.cards) <= set(C56_SCOPE)
        ):
            raise ValueError(
                "human deck must contain eight distinct canonical C56 cards"
            )
        if tuple(sorted(self.cards)) != self.cards:
            raise ValueError("human deck catalog uses sorted canonical card sets")
        return self


class HumanDeckCatalog(Record):
    schema_version: Literal["c56-human-deck-catalog-v1"] = "c56-human-deck-catalog-v1"
    source_role: Literal["train"] = "train"
    index_sha256: SHA
    roles_sha256: SHA
    decks: tuple[HumanDeckFrequency, ...]

    @model_validator(mode="after")
    def unique(self):
        if not self.decks or len({d.cards for d in self.decks}) != len(self.decks):
            raise ValueError(
                "human deck catalog must be nonempty with unique card sets"
            )
        return self


class RootRequestV3(RootRequest):
    card_scope: tuple[str, ...]
    bundle: Bundle
    context: MechanicContext
    own_archetype: str = Field(min_length=1)
    opponent_archetype: str = Field(min_length=1)

    @model_validator(mode="after")
    def scope(self):
        # Overrides the pilot-only validator; episode identity stays inherited.
        if (
            not self.card_scope
            or len(set(self.card_scope)) != len(self.card_scope)
            or not set(self.card_scope) <= set(C56_SCOPE)
        ):
            raise ValueError("declare a distinct canonical C56 card scope")
        if self.start_tick >= self.stop_tick or (self.stop_tick - self.start_tick) % 5:
            raise ValueError("root window must contain whole five-tick intervals")
        for deck in self.decks:
            if (
                len(deck) != 8
                or len(set(deck)) != 8
                or not set(deck) <= set(self.card_scope) | SUPPORTED_CARDS
            ):
                raise ValueError("decks must contain eight distinct scoped cards")
        if not set(self.decks[self.root_owner]) <= set(self.card_scope):
            raise ValueError("own human deck exceeds requested actor scope")
        if (
            self.focal_card not in self.decks[self.root_owner]
            or self.focal_card not in BUNDLES[self.bundle]
        ):
            raise ValueError("focal card must belong to own deck and declared bundle")
        if self.own_archetype != archetype(
            self.decks[self.root_owner]
        ) or self.opponent_archetype != archetype(self.decks[1 - self.root_owner]):
            raise ValueError("archetype label must describe its declared deck")
        if self.context == "air_threat":
            if not set(self.decks[1 - self.root_owner]) & AIR_CARDS:
                raise ValueError("air-threat episodes require an actual air opponent")
        elif not set(self.decks[1 - self.root_owner]) <= SUPPORTED_CARDS:
            raise ValueError("non-air strata use human P16 opponent decks")
        return self


class RootBankV3(Record):
    schema_version: Literal["readiness-v2-root-bank-v3"] = "readiness-v2-root-bank-v3"
    status: Literal["draft_requires_captures"] = "draft_requires_captures"
    public_contract_version: Literal[5] = 5
    master_seed: int = Field(ge=0)
    bundle: Bundle
    card_scope: tuple[str, ...]
    human_catalog_sha256: SHA
    requests: tuple[RootRequestV3, ...]
    conditions: tuple[str, ...] = CONDITIONS
    independence_unit: Literal["one_root_per_separate_full_episode"] = (
        "one_root_per_separate_full_episode"
    )
    missing_rule: Literal["retain_failure_no_replacement"] = (
        "retain_failure_no_replacement"
    )
    ability_rule: Literal["masked"] = "masked"
    deck_rule: Literal["top4_per_eligible_archetype_frequency_weighted"] = (
        "top4_per_eligible_archetype_frequency_weighted"
    )

    @model_validator(mode="after")
    def design(self):
        if len(self.requests) != 32 or self.conditions != CONDITIONS:
            raise ValueError(
                "32 episodes and the four declared continuation pairs are required"
            )
        for field in (
            "family_id",
            "source_episode_id",
            "episode_seed",
            "episode_design_sha256",
        ):
            if len({getattr(r, field) for r in self.requests}) != 32:
                raise ValueError(f"duplicate {field}; no sibling roots or replacements")
        if Counter(r.root_owner for r in self.requests) != {0: 16, 1: 16}:
            raise ValueError("root owners must balance seats")
        focals = set(BUNDLES[self.bundle]) & set(self.card_scope)
        counts = Counter(r.focal_card for r in self.requests)
        if set(counts) != focals or any(not 2 <= n <= 4 for n in counts.values()):
            raise ValueError("each scoped bundle card needs two to four focal episodes")
        for request in self.requests:
            if request.bundle != self.bundle or request.card_scope != self.card_scope:
                raise ValueError("request scope and bundle must match the bank")
            if request.prefix_owner_min_elixir != 8 or request.stop_tick != 3600:
                raise ValueError("v3 declares reserve8 and stop tick3600")
        return self


def _choose(pool, rng, sample):
    grouped = defaultdict(list)
    for deck in pool:
        grouped[archetype(deck.cards)].append(deck)
    if not grouped:
        raise ValueError(
            "no eligible human deck; do not synthesize or replace the request"
        )
    families = sorted(grouped, key=lambda k: (-max(d.frequency for d in grouped[k]), k))
    family = families[sample % len(families)]
    top = sorted(grouped[family], key=lambda d: (-d.frequency, d.cards))[:4]
    return rng.choices(top, weights=[d.frequency for d in top], k=1)[0]


def _context(focal):
    if focal in {"Miner", "GoblinBarrel"}:
        return "enemy_side_deployment"
    if focal in {"GoblinHut", "BombTower", "InfernoTower"}:
        return "building_pull"
    if focal in set(BUNDLES["B1"]) - {"ElectroSpirit"}:
        return "spell_value"
    if focal in {
        "BabyDragon",
        "Minions",
        "Bats",
        "MinionHorde",
        "Wizard",
        "Princess",
        "Firecracker",
        "BlowdartGoblin",
        "FirespiritHut",
        "ElectroSpirit",
    }:
        return "air_threat"
    if focal in {"Golem", "RoyalHogs", "Wallbreakers", "Balloon", "Xbow"}:
        return "enemy_backline"
    return "own_half_threat"


def generate_root_bank_v3(
    master_seed: int,
    catalog: HumanDeckCatalog,
    bundle: Bundle,
    *,
    card_scope: tuple[str, ...] = C56_SCOPE,
) -> RootBankV3:
    if type(master_seed) is not int or master_seed < 0:
        raise ValueError("master seed must be a nonnegative integer")
    if bundle not in BUNDLES:
        raise ValueError("unknown mechanic bundle")
    if len(set(card_scope)) != len(card_scope) or not set(card_scope) <= set(C56_SCOPE):
        raise ValueError("invalid C56 card scope")
    card_scope = tuple(sorted(card_scope))
    focals = sorted(set(BUNDLES[bundle]) & set(card_scope))
    if not 8 <= len(focals) <= 16:
        raise ValueError("32-family bank requires 8-16 focal cards for the 2-4 quota")
    own_pool = [d for d in catalog.decks if set(d.cards) <= set(card_scope)]
    pilot_pool = [d for d in catalog.decks if set(d.cards) <= SUPPORTED_CARDS]
    air_pool = [d for d in own_pool if set(d.cards) & AIR_CARDS]
    source = random.Random(f"v3:{master_seed}:{bundle}")
    requests = []
    used = set()
    occurrences = Counter()
    for index in range(32):
        focal = focals[index % len(focals)]
        sample = occurrences[focal]
        occurrences[focal] += 1
        seed = source.getrandbits(32)
        if seed in used:
            raise ValueError("episode seed collision; no redraw")
        used.add(seed)
        rng = random.Random(seed)
        # First two passes cover both seats per focal. Extra slots balance globally.
        owner = (sample if sample < 2 else index) % 2
        context = _context(focal)
        own = _choose([d for d in own_pool if focal in d.cards], rng, sample)
        other = _choose(air_pool if context == "air_threat" else pilot_pool, rng, index)
        a, b = list(own.cards), list(other.cards)
        rng.shuffle(a)
        rng.shuffle(b)
        decks = (tuple(a), tuple(b)) if owner == 0 else (tuple(b), tuple(a))
        key = f"v3-{bundle}-m{master_seed}-episode-{index:02d}"
        requests.append(
            RootRequestV3(
                family_id=key,
                source_episode_id=key,
                root_owner=owner,
                episode_seed=seed,
                decks=decks,
                prefix_styles=(
                    rng.choice(("balanced", "pressure", "defense")),
                    rng.choice(("balanced", "pressure", "defense")),
                ),
                focal_card=focal,
                context=context,
                card_scope=card_scope,
                bundle=bundle,
                own_archetype=archetype(own.cards),
                opponent_archetype=archetype(other.cards),
                prefix_owner_min_elixir=8.0,
                stop_tick=3600,
            )
        )
    return RootBankV3(
        master_seed=master_seed,
        bundle=bundle,
        card_scope=card_scope,
        human_catalog_sha256=canonical_sha(catalog.model_dump(mode="json")),
        requests=tuple(requests),
    )


def context_matches_v3(context, controller, packet):
    packet.validate()
    if context not in {
        "air_threat",
        "building_pull",
        "spell_value",
        "enemy_side_deployment",
    }:
        return context_matches(context, controller, packet)
    if context == "spell_value":
        return context_matches("enemy_cluster", controller, packet)
    if context == "enemy_side_deployment":
        mask = controller.mask_builder.build(
            PublicActionMaskInput.from_confidence_observation(packet)
        )
        return any(
            d.action_id < 2304 and d.action_id % 576 // 18 >= 16 and mask[d.action_id]
            for d in controller.ranked_plays(packet)
        )
    # Geometry, identity and levels are checked by the public-only body reader.
    bodies = controller._bodies(packet)
    obs = packet.observation
    indices = [
        i
        for i in np.flatnonzero(obs.entity_mask)
        if sum(obs.entity_features[i, 4:6]) >= 0.5
    ]
    for body, index in zip(bodies, indices):
        if not body.enemy or body.crown or body.y >= 19:
            continue
        stats = controller.bodies.get(int(obs.entity_ids[index]))
        if context == "air_threat" and stats is not None and is_air_unit_card(stats):
            return True
        if context == "building_pull" and body.targets_buildings:
            return True
    return False


def select_root_v3(
    request: RootRequestV3,
    controller: PublicScriptedOpponent,
    packets: Iterable[tuple[int, ConfidenceAwareActorObservation]],
) -> RootSelection:
    if controller.card_scope != "c56" or controller.builder.card_semantics_version != 5:
        raise ValueError("v3 requires the explicit C56 controller and contract v5")
    return select_root(
        request, controller, packets, context_predicate=context_matches_v3
    )
