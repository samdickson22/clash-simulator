"""Prospective episode requests and causal root selection for readiness v2.

A request is not a captured root or evidence of statistical independence. Each
request needs its own complete episode and exposure-ledger binding. Candidate
selection sees public packets only; it never sees branch outcomes.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable
from typing import Literal

import numpy as np
from pydantic import Field, model_validator

from .public_observation import ConfidenceAwareActorObservation
from .public_scripted_opponent import SUPPORTED_CARDS, PublicScriptedOpponent
from .readiness_execution import canonical_sha, packet_sha
from .training_readiness_v2 import (
    CONDITIONS,
    SHA,
    Candidate,
    Record,
    generate_candidates,
)

Context = Literal[
    "own_half_threat", "bridge_contact", "enemy_cluster", "contested_board", "enemy_backline"
]
Style = Literal["balanced", "pressure", "defense"]

# Recognizable deck families within the council's sixteen-card pilot scope.
DECKS = (
    (
        "HogRider",
        "Musketeer",
        "Cannon",
        "Skeletons",
        "IceGolem",
        "IceSpirit",
        "Fireball",
        "Log",
    ),
    (
        "Giant",
        "Prince",
        "DarkPrince",
        "Musketeer",
        "Archers",
        "Goblins",
        "Fireball",
        "Zap",
    ),
    (
        "HogRider",
        "Prince",
        "Knight",
        "Goblins",
        "Tesla",
        "IceSpirit",
        "Fireball",
        "Log",
    ),
    (
        "Giant",
        "Knight",
        "Musketeer",
        "Archers",
        "Cannon",
        "Skeletons",
        "IceGolem",
        "Zap",
    ),
)


class RootRequest(Record):
    family_id: str = Field(min_length=1)
    source_episode_id: str = Field(min_length=1)
    root_owner: Literal[0, 1]
    episode_seed: int = Field(ge=0, lt=2**32)
    decks: tuple[tuple[str, ...], tuple[str, ...]]
    prefix_styles: tuple[Style, Style]
    focal_card: str
    context: Context
    # Native tick coordinates; the first playable native tick is 90.
    start_tick: int = Field(default=90, ge=90)
    stop_tick: int = Field(default=1290, le=6000)
    cadence_ticks: Literal[5] = 5
    level: Literal[11] = 11
    # Legacy saved requests omit this field and retain their unrestricted prefix.
    prefix_owner_min_elixir: float = Field(default=0.0, ge=0, le=10)
    root_rule: Literal["first_public_eligible_focal_candidate"] = (
        "first_public_eligible_focal_candidate"
    )

    @model_validator(mode="after")
    def scope(self) -> RootRequest:
        if self.start_tick >= self.stop_tick or (self.stop_tick - self.start_tick) % 5:
            raise ValueError("root window must contain whole five-tick intervals")
        for deck in self.decks:
            if (
                len(deck) != 8
                or len(set(deck)) != 8
                or not set(deck) <= SUPPORTED_CARDS
            ):
                raise ValueError("each deck needs eight distinct supported pilot cards")
        if self.focal_card not in self.decks[self.root_owner]:
            raise ValueError("focal card must belong to the root owner")
        return self

    @property
    def episode_design_sha256(self) -> str:
        # Excludes cosmetic identifiers so renaming cannot disguise reuse.
        design = {
            "seed": self.episode_seed,
            "decks": self.decks,
            "prefix_styles": self.prefix_styles,
            "level": self.level,
        }
        # Preserve the original episode identity for old unrestricted requests.
        if self.prefix_owner_min_elixir:
            design["prefix_owner_min_elixir"] = self.prefix_owner_min_elixir
        return canonical_sha(design)


class RootBank(Record):
    schema_version: Literal["readiness-v2-root-bank-v1", "readiness-v2-root-bank-v2"] = "readiness-v2-root-bank-v2"
    status: Literal["draft_requires_captures"] = "draft_requires_captures"
    master_seed: int = Field(ge=0)
    requests: tuple[RootRequest, ...]
    conditions: tuple[str, ...] = CONDITIONS
    independence_unit: Literal["one_root_per_separate_full_episode"] = (
        "one_root_per_separate_full_episode"
    )
    missing_rule: Literal["retain_failure_no_replacement"] = (
        "retain_failure_no_replacement"
    )

    @model_validator(mode="after")
    def design(self) -> RootBank:
        if self.schema_version == "readiness-v2-root-bank-v2":
            if any(r.prefix_owner_min_elixir != 8 or r.stop_tick != 3600 for r in self.requests):
                raise ValueError("root-bank v2 requires declared owner prefix reserve8 and stop tick3600")
            if any(r.focal_card in OFFENSIVE_FOCAL_CARDS and r.context != "enemy_backline" for r in self.requests):
                raise ValueError("offensive focal requests require enemy-backline context")
        if len(self.requests) != 32:
            raise ValueError("exactly 32 prospective episode requests required")
        if self.conditions != CONDITIONS:
            raise ValueError("the four agreed reacting continuation pairs are required")
        for name in (
            "family_id",
            "source_episode_id",
            "episode_seed",
            "episode_design_sha256",
        ):
            if len({getattr(r, name) for r in self.requests}) != 32:
                raise ValueError(
                    f"duplicate {name}: variants cannot become independent families"
                )
        if Counter(r.root_owner for r in self.requests) != {0: 16, 1: 16}:
            raise ValueError("root owners must balance seats")
        if Counter(r.focal_card for r in self.requests) != dict.fromkeys(
            SUPPORTED_CARDS, 2
        ):
            raise ValueError("each pilot card requires two focal requests")
        return self


OFFENSIVE_FOCAL_CARDS = frozenset({"Giant", "HogRider", "Fireball", "Log", "Zap"})


def generate_root_bank(master_seed: int) -> RootBank:
    """Declare stratified independent episodes, without collecting any outcomes.

    Each request draws a new episode seed, two decks and two independent deck
    permutations. There is no mirrored second seat or modified sibling root.
    The declarations narrow admission to the stated public eligibility rule.
    """
    if type(master_seed) is not int or master_seed < 0:
        raise ValueError("master seed must be a nonnegative integer")
    source = random.Random(master_seed)
    contexts: tuple[Context, ...] = (
        "own_half_threat",
        "bridge_contact",
        "enemy_cluster",
        "contested_board",
    )
    requests: list[RootRequest] = []
    seen_seeds: set[int] = set()
    for i, focal in enumerate(sorted(SUPPORTED_CARDS)):
        for sample in range(2):
            seed = source.getrandbits(32)
            if seed in seen_seeds:
                # Failure is visible; no silently redrawn episode.
                raise ValueError(
                    "episode seed collision; declare a new bank before collection"
                )
            seen_seeds.add(seed)
            rng = random.Random(seed)
            owner: Literal[0, 1] = 0 if (i + sample) % 2 == 0 else 1
            own = list(rng.choice([d for d in DECKS if focal in d]))
            other = list(rng.choice(DECKS))
            rng.shuffle(own)
            rng.shuffle(other)
            decks = (
                (tuple(own), tuple(other)) if owner == 0 else (tuple(other), tuple(own))
            )
            style_options: tuple[Style, ...] = ("balanced", "pressure", "defense")
            styles = (rng.choice(style_options), rng.choice(style_options))
            key = f"m{master_seed}-episode-{len(requests):02d}"
            requests.append(
                RootRequest(
                    family_id=key,
                    source_episode_id=key,
                    root_owner=owner,
                    episode_seed=seed,
                    decks=decks,
                    prefix_styles=styles,
                    focal_card=focal,
                    context=("enemy_backline" if focal in OFFENSIVE_FOCAL_CARDS
                             else contexts[(i + 2 * sample) % len(contexts)]),
                    prefix_owner_min_elixir=8.0,
                    stop_tick=3600,
                )
            )
    return RootBank(master_seed=master_seed, requests=tuple(requests))


def context_matches(
    context: Context,
    controller: PublicScriptedOpponent,
    packet: ConfidenceAwareActorObservation,
) -> bool:
    """Recognize public board geometry, without consulting private state."""
    obs = packet.observation
    body_rows = obs.entity_mask & (obs.entity_features[:, 4] > 0.5)
    rows = obs.entity_features[body_rows]
    confidence = packet.entity_feature_confidence[body_rows]
    if len(rows) == 0 or np.any(confidence[:, :6] < 1):
        return False
    enemies = rows[rows[:, 3] > 0.5]
    friends = rows[rows[:, 2] > 0.5]
    if context == "enemy_backline":
        # The public scorer calls y<17 incoming. Require at least one visible
        # enemy troop and no enemy troop in that incoming region, rather than
        # asking offensive cards to win a defensive candidate-ranking contest.
        return bool(len(enemies) and np.all(enemies[:, 1] * 32 >= 17.0))
    if context == "own_half_threat":
        return bool(np.any(enemies[:, 1] < 0.5))
    if context == "bridge_contact":
        return bool(np.any(np.abs(enemies[:, 1] * 32 - 16) <= 3))
    if context == "contested_board":
        return bool(len(enemies) and len(friends))
    if context == "enemy_cluster":
        if len(enemies) < 2:
            return False
        positions = enemies[:, :2] * np.array([18, 32])
        distances = np.sum((positions[:, None] - positions[None, :]) ** 2, axis=-1)
        return bool(np.any((distances <= 9) & ~np.eye(len(enemies), dtype=bool)))
    raise ValueError("unsupported public tactical context")


def apply_prefix_owner_reserve(
    request: RootRequest,
    owner: int,
    packet: ConfidenceAwareActorObservation,
    ordinary_action: int,
) -> int:
    """Apply only the declared root-owner prefix reserve, never a branch rule.

    This changes prefix exploration and narrows the generation distribution.
    It neither requires high elixir at selected roots nor changes candidate
    generation, reacting continuation controllers or action rankings.
    """
    if type(owner) is not int or owner not in (0, 1):
        raise ValueError("prefix owner must be zero or one")
    if owner != request.root_owner or request.prefix_owner_min_elixir == 0:
        return ordinary_action
    confidence = packet.global_feature_confidence[5]
    own_elixir = float(packet.observation.global_features[5]) * 10
    if confidence <= 0 or own_elixir < request.prefix_owner_min_elixir:
        return 2304
    return ordinary_action


class RootSelection(Record):
    family_id: str
    source_episode_id: str
    root_owner: Literal[0, 1]
    status: Literal[
        "selected", "no_eligible_root", "missing_packets", "terminal_before_root"
    ]
    root_tick: int | None = None
    public_packet_sha256: SHA | None = None
    candidates: tuple[Candidate, ...] = ()
    original_recommendation: int | None = None
    observed_packets: int = Field(ge=0)
    reason: str


def select_root(
    request: RootRequest,
    controller: PublicScriptedOpponent,
    packets: Iterable[tuple[int, ConfidenceAwareActorObservation]],
    *,
    context_predicate=context_matches,
) -> RootSelection:
    """Select the first eligible root; never replace it using continuation results.

    Input packets must be projected for request.root_owner and use native ticks.
    Every five-tick packet in the declared scan window must exist until selection.
    No later packets or branch outcomes are needed after a root is selected.
    """
    count = 0

    def result(
        status: Literal[
            "selected", "no_eligible_root", "missing_packets", "terminal_before_root"
        ],
        reason: str,
        *,
        root_tick: int | None = None,
        public_packet_sha256: str | None = None,
        candidates: tuple[Candidate, ...] = (),
        original_recommendation: int | None = None,
    ) -> RootSelection:
        return RootSelection(
            family_id=request.family_id,
            source_episode_id=request.source_episode_id,
            root_owner=request.root_owner,
            status=status,
            observed_packets=count,
            reason=reason,
            root_tick=root_tick,
            public_packet_sha256=public_packet_sha256,
            candidates=candidates,
            original_recommendation=original_recommendation,
        )

    expected = request.start_tick
    focal_token = controller.builder.token_id(
        request.focal_card, namespace="card_action"
    )
    for tick, packet in packets:
        if tick != expected:
            return result(
                "missing_packets", f"expected tick {expected}, received {tick}"
            )
        count += 1
        packet.validate()
        if packet.observation.terminal is True:
            return result(
                "terminal_before_root", "episode ended before an eligible root"
            )
        if context_predicate(request.context, controller, packet):
            try:
                candidates = generate_candidates(controller, packet)
            except ValueError as exc:
                if not str(exc).startswith("ineligible root:"):
                    raise
                candidates = ()
            if candidates and focal_token in {c.card_token for c in candidates}:
                return result(
                    "selected",
                    "first eligible public tactical root",
                    root_tick=tick,
                    public_packet_sha256=packet_sha(packet),
                    candidates=candidates,
                    original_recommendation=controller.decide(packet).action_id,
                )
        if tick == request.stop_tick:
            return result(
                "no_eligible_root",
                "bounded public root window exhausted; no replacement",
            )
        expected += request.cadence_ticks
    return result("missing_packets", f"missing tick {expected}")
