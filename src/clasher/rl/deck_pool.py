from __future__ import annotations

from collections import deque
import json
import random
from pathlib import Path
from typing import List, Sequence, Tuple

from clasher.player import PlayerState


def load_deck_pool(path: str | Path = "decks.json") -> List[List[str]]:
    deck_path = Path(path)
    with deck_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    decks: List[List[str]] = []
    for raw_deck in payload.get("decks", []):
        cards = list(raw_deck.get("cards", []))
        if len(cards) >= 8:
            decks.append(cards[:8])

    if not decks:
        raise ValueError(f"No decks found in {deck_path}")
    return decks


def unique_cards_from_decks(decks: Sequence[Sequence[str]]) -> List[str]:
    return sorted({card for deck in decks for card in deck})


def apply_deck_to_player(player: PlayerState, deck: Sequence[str], rng: random.Random) -> None:
    if len(deck) < 8:
        raise ValueError("Deck must contain at least 8 cards")

    shuffled = list(deck[:8])
    rng.shuffle(shuffled)

    player.deck = shuffled
    player.hand = shuffled[:4]
    player.cycle_queue = deque(shuffled[4:])


def sample_decks(
    decks: Sequence[Sequence[str]],
    rng: random.Random,
    mirror_match: bool = False,
) -> Tuple[List[str], List[str]]:
    first = list(rng.choice(decks))
    if mirror_match:
        return first, list(first)
    second = list(rng.choice(decks))
    return first, second
