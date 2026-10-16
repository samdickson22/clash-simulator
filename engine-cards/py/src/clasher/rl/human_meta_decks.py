from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .deck_pool import load_deck_pool
from .oracle_corpus import atomic_write_json, file_sha256
from .replay_split import (
    ReplaySplitRecord,
    load_raw_cascade_records,
    normalize_noisy_deck_signatures,
)


@dataclass(frozen=True)
class HumanMetaDeck:
    deck_hash: str
    cards: tuple[str, ...]
    archetype: str
    replays: tuple[str, ...]
    arenas: tuple[str, ...]
    samples: int

    @property
    def occurrences(self) -> int:
        return len(self.replays)

    def as_pool_entry(self, *, sampling_weight: float) -> dict[str, Any]:
        return {
            "name": f"TV Royale {self.archetype} {self.deck_hash[:8]}",
            "cards": list(self.cards),
            "archetype": self.archetype,
            "source": "tv-royale-recurring-exact-deck-v1",
            "deck_hash": self.deck_hash,
            "observed_replays": self.occurrences,
            "observed_samples": self.samples,
            "arenas": list(self.arenas),
            "sampling_weight": sampling_weight,
        }


def select_recurring_human_meta_decks(
    records: Sequence[ReplaySplitRecord],
    *,
    min_replays: int = 2,
) -> tuple[tuple[HumanMetaDeck, ...], dict[str, int]]:
    """Select only repeated, exact, fully enabled human deck observations.

    Signatures are conservatively normalized first, allowing a partial UI
    observation to join a complete eight-card observation. Components whose
    union is over-complete or contains any unmapped card are rejected rather
    than guessed back down to eight cards.
    """
    if min_replays < 2:
        raise ValueError("min_replays must be at least two")
    normalized = normalize_noisy_deck_signatures(records)
    grouped: dict[tuple[str, ...], list[ReplaySplitRecord]] = {}
    for record in normalized:
        grouped.setdefault(record.deck_signature, []).append(record)

    rejected: Counter[str] = Counter()
    selected: list[HumanMetaDeck] = []
    for signature, group in sorted(grouped.items()):
        replays = tuple(sorted({record.replay for record in group}))
        if len(replays) < min_replays:
            rejected["too_few_replays"] += 1
            continue
        if len(signature) != 8:
            rejected["not_exactly_eight_signature_items"] += 1
            continue
        if any(not item.startswith("enabled:") for item in signature):
            rejected["contains_unmapped_card"] += 1
            continue
        cards = tuple(item.removeprefix("enabled:") for item in signature)
        if len(set(cards)) != 8:
            rejected["not_eight_unique_enabled_cards"] += 1
            continue
        archetypes = {record.archetype for record in group}
        if len(archetypes) != 1:
            rejected["inconsistent_archetype"] += 1
            continue
        deck_hash = hashlib.sha256("\0".join(signature).encode()).hexdigest()
        selected.append(
            HumanMetaDeck(
                deck_hash=deck_hash,
                cards=cards,
                archetype=next(iter(archetypes)),
                replays=replays,
                arenas=tuple(sorted({record.arena for record in group})),
                samples=sum(record.samples for record in group),
            )
        )
    selected.sort(key=lambda deck: (-deck.occurrences, deck.deck_hash))
    return tuple(selected), dict(sorted(rejected.items()))


def publish_human_meta_deck_gate(
    *,
    run_manifest_path: Path,
    output_dir: Path,
    decks_path: Path,
    target_games: int | None,
    min_replays: int = 2,
) -> dict[str, Any]:
    """Publish uniform and observed-frequency views of a frozen deck gate."""
    source_sha256_before = file_sha256(run_manifest_path)
    raw_records = load_raw_cascade_records(
        run_manifest_path,
        decks_path=decks_path,
        target_games=target_games,
    )
    decks, rejected = select_recurring_human_meta_decks(
        raw_records,
        min_replays=min_replays,
    )
    if not decks:
        raise ValueError("no recurring exact fully enabled decks passed the gate")
    source_sha256_after = file_sha256(run_manifest_path)
    if source_sha256_before != source_sha256_after:
        raise RuntimeError("run manifest changed while the human-meta gate was built")

    normalized = normalize_noisy_deck_signatures(raw_records)
    common_metadata = {
        "source_run_manifest": str(run_manifest_path.resolve()),
        "source_run_manifest_sha256": source_sha256_after,
        "source_games": len(raw_records),
        "min_replays": min_replays,
        "selection_policy": (
            "recurring-conservative-component-exact8-fully-enabled-v1"
        ),
        "training_action_labels_used": False,
        "intended_use": "final-evaluation-only",
    }
    uniform_payload = {
        "schema_version": 1,
        "metadata": {**common_metadata, "weighting": "uniform-per-deck"},
        "decks": [deck.as_pool_entry(sampling_weight=1.0) for deck in decks],
    }
    frequency_payload = {
        "schema_version": 1,
        "metadata": {
            **common_metadata,
            "weighting": "observed-replay-frequency",
        },
        "decks": [
            deck.as_pool_entry(sampling_weight=float(deck.occurrences))
            for deck in decks
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    uniform_path = output_dir / "uniform.json"
    frequency_path = output_dir / "frequency_weighted.json"
    atomic_write_json(uniform_path, uniform_payload)
    atomic_write_json(frequency_path, frequency_payload)
    # Loading both artifacts exercises the exact production parser and rejects
    # malformed or short decks before the gate can be used by an evaluation.
    load_deck_pool(uniform_path)
    load_deck_pool(frequency_path)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        **common_metadata,
        "raw_deck_signatures": len(
            {record.deck_signature for record in raw_records}
        ),
        "conservative_components": len(
            {record.deck_signature for record in normalized}
        ),
        "selected_decks": len(decks),
        "selected_replays": sum(deck.occurrences for deck in decks),
        "selected_samples": sum(deck.samples for deck in decks),
        "selected_archetypes": dict(
            sorted(Counter(deck.archetype for deck in decks).items())
        ),
        "rejected_components": rejected,
        "artifacts": {
            "uniform": {
                "path": str(uniform_path.resolve()),
                "sha256": file_sha256(uniform_path),
            },
            "frequency_weighted": {
                "path": str(frequency_path.resolve()),
                "sha256": file_sha256(frequency_path),
            },
        },
        "decks": [
            {
                "deck_hash": deck.deck_hash,
                "cards": list(deck.cards),
                "archetype": deck.archetype,
                "replays": list(deck.replays),
                "arenas": list(deck.arenas),
                "samples": deck.samples,
            }
            for deck in decks
        ],
    }
    atomic_write_json(output_dir / "manifest.json", manifest)
    return manifest
