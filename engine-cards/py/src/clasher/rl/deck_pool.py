from __future__ import annotations

import json
import random
from collections import deque
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NamedTuple, cast

from clasher.paths import decks_path as resolve_decks_path
from clasher.player import PlayerState


class DeckMatchup(NamedTuple):
    learner_cards: list[str]
    opponent_cards: list[str]
    weight: float


class DeckPool(list[list[str]]):
    """List-compatible deck pool with optional sampling weights."""

    def __init__(self, decks: Sequence[Sequence[str]], weights: Sequence[float]) -> None:
        super().__init__(list(cards) for cards in decks)
        if len(self) != len(weights):
            raise ValueError("deck and weight counts must match")
        self.weights = tuple(float(weight) for weight in weights)


def load_deck_pool(path: str | Path = "decks.json") -> DeckPool:
    deck_path = resolve_decks_path(path, must_exist=True)
    with deck_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    decks: list[list[str]] = []
    weights: list[float] = []
    for raw_deck in payload.get("decks", []):
        cards = list(raw_deck.get("cards", []))
        if len(cards) >= 8:
            decks.append(cards[:8])
            weight = float(raw_deck.get("sampling_weight", 1.0))
            if weight <= 0.0:
                raise ValueError(f"deck sampling weight must be positive in {deck_path}")
            weights.append(weight)

    if not decks:
        raise ValueError(f"No decks found in {deck_path}")
    return DeckPool(decks, weights)


def load_matchup_pool(path: str | Path) -> list[DeckMatchup]:
    matchup_path = resolve_decks_path(path, must_exist=True)
    with matchup_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    matchups: list[DeckMatchup] = []
    for index, raw_matchup in enumerate(payload.get("matchups", [])):
        learner_cards = list(raw_matchup.get("learner_cards", []))
        opponent_cards = list(raw_matchup.get("opponent_cards", []))
        weight = float(raw_matchup.get("weight", 1.0))
        if len(learner_cards) < 8 or len(opponent_cards) < 8:
            raise ValueError(f"matchup {index} must contain two eight-card decks")
        if weight <= 0.0:
            raise ValueError(f"matchup {index} weight must be positive")
        matchups.append(
            DeckMatchup(learner_cards[:8], opponent_cards[:8], weight)
        )
    if not matchups:
        raise ValueError(f"No matchups found in {matchup_path}")
    return matchups


def unique_cards_from_decks(decks: Sequence[Sequence[str]]) -> list[str]:
    return sorted({card for deck in decks for card in deck})


def apply_deck_to_player(
    player: PlayerState, deck: Sequence[str], rng: random.Random,
    *, card_levels: Mapping[str, int] | None = None,
) -> None:
    if len(deck) < 8:
        raise ValueError("Deck must contain at least 8 cards")

    shuffled = list(deck[:8])
    rng.shuffle(shuffled)

    apply_ordered_deck_to_player(player, shuffled, card_levels=card_levels)


def apply_ordered_deck_to_player(
    player: PlayerState,
    deck: Sequence[str],
    *, card_levels: Mapping[str, int] | None = None,
) -> None:
    """Install an already-shuffled deck without consuming battle RNG."""
    if len(deck) < 8:
        raise ValueError("Deck must contain at least 8 cards")

    ordered = list(deck[:8])
    player.set_card_levels(card_levels or {})
    player.deck = ordered
    player.hand = cast(list[str | None], ordered[:4])
    player.cycle_queue = deque(ordered[4:])
    player.next_card_refill_cooldown_ms = 0


def sample_decks(
    decks: Sequence[Sequence[str]],
    rng: random.Random,
    mirror_match: bool = False,
) -> tuple[list[str], list[str]]:
    first = sample_deck(decks, rng)
    if mirror_match:
        return first, list(first)
    return first, sample_deck(decks, rng)


def sample_deck(
    decks: Sequence[Sequence[str]],
    rng: random.Random,
) -> list[str]:
    """Sample one deck while preserving unweighted RNG behavior."""

    weights = decks.weights if isinstance(decks, DeckPool) else None
    weighted = weights is not None and any(
        weight != weights[0] for weight in weights[1:]
    )
    return list(
        rng.choices(decks, weights=weights, k=1)[0]
        if weighted
        else rng.choice(decks)
    )
