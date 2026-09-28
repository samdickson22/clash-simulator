from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from clasher.spells import SPELL_REGISTRY, ProjectileSpell, RollingProjectileSpell

from .common import BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .deck_curriculum import HELD_OUT_ARCHETYPES, infer_archetype
from .imitation import CorpusMetadata, load_corpus
from .imitation_mix import combine_imitation_corpora
from .oracle_corpus import (
    CORPUS_ARRAY_NAMES,
    atomic_save_npz,
    atomic_write_json,
    file_sha256,
)
from .tv_royale_replay import TVRoyalePlacementConverter

STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE = (
    "tv-royale-raw-cascade-location-visual-strict-v3"
)


def complete_visible_hand_mask(hand_ids: np.ndarray) -> NDArray[np.bool_]:
    """Return rows whose four visible hand slots all contain known cards.

    Raw TV Royale action extraction historically allowed a played-card row when
    the target slot mapped into the enabled vocabulary even if another visible
    slot did not. Exact no-op rows already required all four slots to map. A
    split built from those asymmetric rows over-represents plays, so every
    imitation split now applies the same complete-hand requirement to both
    labels. The fifth slot is intentionally ignored because TV Royale does not
    expose a trustworthy next-card label.
    """
    values = np.asarray(hand_ids)
    if values.ndim != 2 or values.shape[1] < 4:
        raise ValueError("hand_ids must have shape [samples, at least four slots]")
    return np.asarray(np.all(values[:, :4] != 0, axis=1), dtype=np.bool_)


def rechain_previous_actions(expert_actions: np.ndarray) -> NDArray[np.int64]:
    """Build recurrent previous-action inputs for one retained episode."""
    values = np.asarray(expert_actions, dtype=np.int64)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("expert actions must be a non-empty one-dimensional array")
    previous = np.empty_like(values)
    previous[0] = NUM_HAND_SLOTS * NUM_TILES
    previous[1:] = values[:-1]
    return previous


@dataclass(frozen=True)
class ReplaySplitRecord:
    replay: str
    arena: str
    arena_number: int
    corpus: Path
    deck_signature: tuple[str, ...]
    enabled_cards: tuple[str, ...]
    archetype: str
    samples: int
    plays: int
    noops: int

    @property
    def deck_hash(self) -> str:
        return hashlib.sha256("\0".join(self.deck_signature).encode()).hexdigest()


@dataclass(frozen=True)
class LocationCorpusRecord:
    """One fail-closed TV Royale deployment-clock sidecar."""

    replay: str
    arena: str
    corpus: Path
    samples: int
    source_samples: int
    sample_mask: NDArray[np.bool_]
    label_source: str


def summarize_location_corpus_diversity(corpus_path: Path) -> dict[str, Any]:
    """Summarize semantic and board coverage in one placement-only corpus.

    Sample and replay counts cannot detect a spatial corpus concentrated on one
    card, lane, or small patch of tiles.  This report is computed from the
    final deduplicated corpus that imitation will actually consume.
    """
    metadata, arrays = load_corpus(corpus_path)
    actions = np.asarray(arrays["expert_actions"], dtype=np.int64)
    placement_limit = NUM_HAND_SLOTS * NUM_TILES
    if actions.ndim != 1 or actions.size == 0:
        raise ValueError("location corpus must contain placement samples")
    if bool(np.any((actions < 0) | (actions >= placement_limit))):
        raise ValueError("location diversity received a non-placement action")

    slots = actions // NUM_TILES
    tiles = actions % NUM_TILES
    tokens = arrays["hand_ids"][np.arange(actions.size), slots]
    cards: Counter[str] = Counter()
    for token in tokens.tolist():
        token_id = int(token)
        if not 0 <= token_id < len(metadata.token_names):
            raise ValueError("location diversity received an invalid card token")
        card = metadata.token_names[token_id]
        if card.startswith("<"):
            raise ValueError("location diversity received an unknown card token")
        cards[card] += 1

    x = tiles % BOARD_WIDTH
    y = tiles // BOARD_WIDTH
    left = int(np.count_nonzero(x < BOARD_WIDTH // 2))
    right = int(actions.size - left)
    persistent_spell_cards = sorted(card for card in cards if card in SPELL_REGISTRY)
    persistent_spell_samples = sum(cards[card] for card in persistent_spell_cards)
    coarse_regions = {
        (int(tile_x) // 3, int(tile_y) // 4)
        for tile_x, tile_y in zip(x.tolist(), y.tolist(), strict=True)
    }
    side_denominator = max(1, int(actions.size))
    return {
        "samples": int(actions.size),
        "distinct_target_cards": len(cards),
        "target_card_counts": dict(sorted(cards.items())),
        "distinct_target_tiles": int(np.unique(tiles).size),
        "distinct_coarse_regions_3x4": len(coarse_regions),
        "covered_x_columns": int(np.unique(x).size),
        "covered_y_rows": int(np.unique(y).size),
        "covered_y_bands_4_rows": int(np.unique(y // 4).size),
        "left_samples": left,
        "right_samples": right,
        "minority_side_fraction": min(left, right) / side_denominator,
        "persistent_area_spell_cards": persistent_spell_cards,
        "persistent_area_spell_samples": int(persistent_spell_samples),
    }


def _canonical_raw_card(raw_name: str) -> str:
    name = raw_name.strip().lower()
    for prefix in ("gray_", "evo_"):
        if name.startswith(prefix):
            name = name.removeprefix(prefix)
    return "".join(character for character in name if character.isalnum())


def _arena_number(arena: str) -> int:
    prefix = "arena_"
    if not arena.startswith(prefix):
        raise ValueError(f"invalid arena label {arena!r}")
    return int(arena.removeprefix(prefix))


def load_raw_cascade_records(
    run_manifest_path: Path,
    *,
    decks_path: Path,
    target_games: int | None = None,
) -> list[ReplaySplitRecord]:
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    converter = TVRoyalePlacementConverter(decks_path=str(decks_path))
    complete = [
        raw for raw in run_manifest.get("records", []) if raw.get("status") == "complete"
    ]
    if target_games is not None:
        if len(complete) < target_games:
            raise ValueError(
                f"run has only {len(complete)} complete games, expected {target_games}"
            )
        complete = complete[:target_games]
    records: list[ReplaySplitRecord] = []
    seen_replays: set[str] = set()
    for raw in complete:
        corpus = Path(str(raw["corpus"])).resolve()
        game_manifest_path = corpus.parent / "manifest.json"
        game_manifest = json.loads(game_manifest_path.read_text(encoding="utf-8"))
        replay = str(game_manifest["replay"])
        if replay in seen_replays:
            raise ValueError(f"duplicate completed replay {replay}")
        seen_replays.add(replay)
        if file_sha256(corpus) != str(game_manifest["corpus"]["sha256"]):
            raise ValueError(f"corpus digest mismatch for replay {replay}")
        raw_deck = tuple(str(value) for value in game_manifest.get("deck", ()))
        enabled_cards = tuple(
            sorted(
                {
                    mapped
                    for value in raw_deck
                    if (mapped := converter.source_card_name(value)) is not None
                }
            )
        )
        signature = tuple(
            sorted(
                {
                    (
                        f"enabled:{mapped}"
                        if (mapped := converter.source_card_name(value)) is not None
                        else f"raw:{_canonical_raw_card(value)}"
                    )
                    for value in raw_deck
                }
            )
        )
        if not signature:
            raise ValueError(f"replay {replay} has no discovered deck signature")
        arena = str(game_manifest["arena"])
        records.append(
            ReplaySplitRecord(
                replay=replay,
                arena=arena,
                arena_number=_arena_number(arena),
                corpus=corpus,
                deck_signature=signature,
                enabled_cards=enabled_cards,
                archetype=infer_archetype(enabled_cards),
                samples=int(game_manifest["corpus"]["statistics"]["samples"]),
                plays=int(game_manifest["accepted_type_events"]),
                noops=int(game_manifest["accepted_noops"]),
            )
        )
    if not records:
        raise ValueError("run manifest contains no completed games")
    return records


def normalize_noisy_deck_signatures(
    records: Sequence[ReplaySplitRecord],
) -> tuple[ReplaySplitRecord, ...]:
    """Conservatively group signatures differing only by recognition omissions.

    A real deck has eight cards, while strict UI discovery can omit a card or
    retain one duplicate misclassification. Exact eight-card variants are not
    merged merely because they differ by one card. Subset/superset signatures
    within two observations are grouped, as are two over-complete signatures
    that share at least eight observations and differ by one item each.
    """
    if not records:
        return ()
    signatures = sorted({record.deck_signature for record in records})
    parents = list(range(len(signatures)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    signature_sets = [frozenset(signature) for signature in signatures]
    for left, left_set in enumerate(signature_sets):
        for right in range(left):
            right_set = signature_sets[right]
            if len(left_set.symmetric_difference(right_set)) > 2:
                continue
            subset_match = left_set <= right_set or right_set <= left_set
            overcomplete_match = (
                len(left_set) >= 9
                and len(right_set) >= 9
                and len(left_set.intersection(right_set)) >= 8
            )
            if subset_match or overcomplete_match:
                union(left, right)

    members: dict[int, list[int]] = {}
    for index in range(len(signatures)):
        members.setdefault(find(index), []).append(index)
    signature_component = {
        signatures[index]: component
        for component, indices in members.items()
        for index in indices
    }
    component_signature = {
        component: tuple(
            sorted(
                {
                    card
                    for index in indices
                    for card in signatures[index]
                }
            )
        )
        for component, indices in members.items()
    }
    component_enabled: dict[int, tuple[str, ...]] = {}
    component_archetype: dict[int, str] = {}
    for component in members:
        component_enabled[component] = tuple(
            sorted(
                {
                    card
                    for record in records
                    if signature_component[record.deck_signature] == component
                    for card in record.enabled_cards
                }
            )
        )
        observed_archetypes = sorted(
            {
                record.archetype
                for record in records
                if signature_component[record.deck_signature] == component
            }
        )
        component_archetype[component] = (
            infer_archetype(component_enabled[component])
            if component_enabled[component]
            else observed_archetypes[0]
        )

    return tuple(
        replace(
            record,
            deck_signature=component_signature[
                signature_component[record.deck_signature]
            ],
            enabled_cards=component_enabled[
                signature_component[record.deck_signature]
            ],
            archetype=component_archetype[
                signature_component[record.deck_signature]
            ],
        )
        for record in records
    )


def exclude_reserved_replays(
    records: Sequence[ReplaySplitRecord],
    reserved_replays: frozenset[str],
) -> tuple[ReplaySplitRecord, ...]:
    """Remove a declared final-evaluation reserve without silently drifting."""
    if not reserved_replays:
        return tuple(records)
    available = {record.replay for record in records}
    missing = reserved_replays.difference(available)
    if missing:
        raise ValueError(
            "reserved replay IDs are absent from the source run: "
            + ", ".join(sorted(missing))
        )
    filtered = tuple(
        record for record in records if record.replay not in reserved_replays
    )
    if not filtered:
        raise ValueError("final-evaluation reserve removed every replay")
    return filtered


def first_completed_replay_ids(
    run_manifest_path: Path,
    count: int,
) -> frozenset[str]:
    """Return the first ``count`` completed replay IDs in manifest order.

    A resumed raw-cascade run can contain failed attempts between completed
    records, so slicing the record list itself does not define a stable data
    boundary.  Completed manifest order is the extraction chronology used by
    ``target_games`` and is therefore the exact boundary between an incumbent
    corpus and newly collected games.
    """
    if count < 0:
        raise ValueError("completed replay reserve count must be non-negative")
    payload = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    completed = [
        str(record["replay"])
        for record in payload.get("records", ())
        if record.get("status") == "complete"
    ]
    if len(completed) < count:
        raise ValueError(
            f"run has only {len(completed)} completed replays, cannot reserve {count}"
        )
    selected = completed[:count]
    if len(set(selected)) != len(selected):
        raise ValueError("completed replay reserve contains duplicate replay IDs")
    return frozenset(selected)


def assign_replay_splits(
    records: Sequence[ReplaySplitRecord],
    *,
    seed: int,
    validation_fraction: float,
    held_out_archetypes: frozenset[str] = HELD_OUT_ARCHETYPES,
    chronology_min_arena: int | None = None,
) -> dict[str, tuple[ReplaySplitRecord, ...]]:
    """Assign complete deck groups to train, validation, and independent tests.

    Priority is whole-archetype test, then latest-arena chronology test, then a
    deck-signature-disjoint validation split stratified by archetype. If one
    deck signature occurs in several replays, every occurrence follows the
    same assignment.
    """
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be in (0, 1)")
    records = normalize_noisy_deck_signatures(records)
    by_deck: dict[tuple[str, ...], list[ReplaySplitRecord]] = {}
    for record in records:
        by_deck.setdefault(record.deck_signature, []).append(record)
    assignments: dict[str, list[ReplaySplitRecord]] = {
        "train": [],
        "validation": [],
        "archetype_test": [],
        "chronology_test": [],
    }
    eligible_by_archetype: dict[
        str, list[tuple[tuple[str, ...], list[ReplaySplitRecord]]]
    ] = {}
    for signature, group in sorted(by_deck.items()):
        archetypes = {record.archetype for record in group}
        if len(archetypes) != 1:
            raise ValueError("one deck signature maps to multiple archetypes")
        archetype = next(iter(archetypes))
        if archetype in held_out_archetypes:
            assignments["archetype_test"].extend(group)
        elif chronology_min_arena is not None and any(
            record.arena_number >= chronology_min_arena for record in group
        ):
            assignments["chronology_test"].extend(group)
        else:
            eligible_by_archetype.setdefault(archetype, []).append((signature, group))

    for archetype, groups in sorted(eligible_by_archetype.items()):
        ranked = sorted(
            groups,
            key=lambda item: hashlib.sha256(
                f"{seed}:{archetype}:".encode() + "\0".join(item[0]).encode()
            ).digest(),
        )
        if len(ranked) == 1:
            assignments["train"].extend(ranked[0][1])
            continue
        target = max(1, round(sum(len(group) for _, group in ranked) * validation_fraction))
        validation_groups: set[tuple[str, ...]] = set()
        validation_replays = 0
        for signature, group in ranked[:-1]:
            if validation_replays >= target:
                break
            validation_groups.add(signature)
            validation_replays += len(group)
        for signature, group in ranked:
            split = "validation" if signature in validation_groups else "train"
            assignments[split].extend(group)

    result = {
        name: tuple(sorted(values, key=lambda record: record.replay))
        for name, values in assignments.items()
    }
    assigned_replays = [record.replay for values in result.values() for record in values]
    if len(assigned_replays) != len(records) or len(set(assigned_replays)) != len(records):
        raise AssertionError("every replay must be assigned exactly once")
    deck_sets = {
        name: {record.deck_signature for record in values}
        for name, values in result.items()
    }
    for left, left_decks in deck_sets.items():
        for right, right_decks in deck_sets.items():
            if left < right and left_decks.intersection(right_decks):
                raise AssertionError(f"deck overlap between {left} and {right}")
    if {record.archetype for record in result["train"]}.intersection(
        held_out_archetypes
    ):
        raise AssertionError("held-out archetype leaked into training")
    return result


def _publish_split(
    records: Sequence[ReplaySplitRecord],
    *,
    split_name: str,
    output_path: Path,
    seed: int,
) -> dict[str, Any]:
    if not records:
        raise ValueError(f"{split_name} has no replays")
    combined: dict[str, list[np.ndarray]] = {name: [] for name in CORPUS_ARRAY_NAMES}
    provenance: dict[str, list[np.ndarray]] = {
        name: [] for name in ("source_replays", "source_frames", "source_arenas")
    }
    reference: CorpusMetadata | None = None
    published_records: list[ReplaySplitRecord] = []
    source_samples = 0
    rows_removed_incomplete_hand = 0
    noop_action = NUM_HAND_SLOTS * NUM_TILES
    for record in records:
        metadata, arrays = load_corpus(record.corpus)
        source_samples += metadata.samples
        if reference is None:
            reference = metadata
        elif (
            metadata.token_names != reference.token_names
            or metadata.max_entities != reference.max_entities
            or metadata.reward_profile != reference.reward_profile
        ):
            raise ValueError("split sources use incompatible corpus schemas")
        with np.load(record.corpus, allow_pickle=False) as payload:
            for name, parts in provenance.items():
                values = payload[name].copy()
                if values.shape != (metadata.samples,):
                    raise ValueError(f"invalid {name} for replay {record.replay}")
                parts.append(values)
        if np.unique(arrays["episode_ids"]).size != 1:
            raise ValueError(f"replay {record.replay} contains multiple episodes")
        keep = complete_visible_hand_mask(arrays["hand_ids"])
        rows_removed_incomplete_hand += int((~keep).sum())
        if not np.any(keep):
            for parts in provenance.values():
                parts.pop()
            continue
        episode_id = len(published_records)
        published_records.append(record)
        for name, parts in provenance.items():
            parts[-1] = parts[-1][keep]
        for name in CORPUS_ARRAY_NAMES:
            values = arrays[name][keep]
            if name == "episode_ids":
                values = np.full(values.shape, episode_id, dtype=np.int64)
            elif name == "episode_starts":
                values = np.zeros(values.shape, dtype=np.bool_)
                values[0] = True
            elif name == "previous_actions":
                values = rechain_previous_actions(arrays["expert_actions"][keep])
            elif name == "entity_features":
                values = values.astype(np.float16, copy=False)
            combined[name].append(values)
    if reference is None or not published_records:
        raise ValueError(f"{split_name} has no complete-visible-hand rows")
    arrays = {name: np.concatenate(parts, axis=0) for name, parts in combined.items()}
    provenance_arrays = {
        name: np.concatenate(parts, axis=0) for name, parts in provenance.items()
    }
    samples = int(arrays["expert_actions"].shape[0])
    if not np.all(
        arrays["action_masks"][np.arange(samples), arrays["expert_actions"]]
    ):
        raise ValueError(f"{split_name} contains an illegal expert action")
    metadata = replace(
        reference,
        seed=seed,
        decisions=samples,
        samples=samples,
        workers=1,
        behavior_checkpoint=None,
        behavior_opponent=None,
        label_source=(
            f"tv-royale-raw-cascade-{split_name}-complete-hand-type-only-v2"
        ),
    )
    payload = dict(arrays)
    payload.update(provenance_arrays)
    payload["metadata_json"] = np.asarray(metadata.to_json())
    atomic_save_npz(output_path, payload)
    return {
        "output": str(output_path.resolve()),
        "output_sha256": file_sha256(output_path),
        "replays": len(published_records),
        "source_replays_considered": len(records),
        "replays_removed_no_complete_hand": len(records) - len(published_records),
        "deck_signatures": len(
            {record.deck_signature for record in published_records}
        ),
        "source_samples": source_samples,
        "samples": samples,
        "rows_removed_incomplete_visible_hand": rows_removed_incomplete_hand,
        "plays": int(np.count_nonzero(arrays["expert_actions"] != noop_action)),
        "noops": int(np.count_nonzero(arrays["expert_actions"] == noop_action)),
        "arenas": dict(
            sorted(Counter(record.arena for record in published_records).items())
        ),
        "archetypes": dict(
            sorted(Counter(record.archetype for record in published_records).items())
        ),
        "replay_ids": [record.replay for record in published_records],
        "deck_hashes": sorted(
            {record.deck_hash for record in published_records}
        ),
        "metadata": asdict(metadata),
    }


def build_raw_cascade_splits(
    *,
    run_manifest_path: Path,
    output_dir: Path,
    decks_path: Path,
    seed: int,
    validation_fraction: float,
    held_out_archetypes: frozenset[str] = HELD_OUT_ARCHETYPES,
    chronology_min_arena: int | None = None,
    target_games: int | None = None,
    reserved_replays: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    raw_records = load_raw_cascade_records(
        run_manifest_path, decks_path=decks_path, target_games=target_games
    )
    normalized_records = normalize_noisy_deck_signatures(raw_records)
    records = exclude_reserved_replays(normalized_records, reserved_replays)
    assignments = assign_replay_splits(
        records,
        seed=seed,
        validation_fraction=validation_fraction,
        held_out_archetypes=held_out_archetypes,
        chronology_min_arena=chronology_min_arena,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    split_records = {
        name: _publish_split(
            split,
            split_name=name,
            output_path=output_dir / f"{name}.npz",
            seed=seed,
        )
        for name, split in assignments.items()
        if split
    }
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "source_run_manifest": str(run_manifest_path.resolve()),
        "source_run_manifest_sha256": file_sha256(run_manifest_path),
        "seed": seed,
        "validation_fraction": validation_fraction,
        "held_out_archetypes": sorted(held_out_archetypes),
        "chronology_min_arena": chronology_min_arena,
        "source_replays": len(normalized_records),
        "reserved_final_evaluation_replays": len(reserved_replays),
        "reserved_replay_ids": sorted(reserved_replays),
        "total_replays": sum(
            int(split["replays"]) for split in split_records.values()
        ),
        "source_samples": sum(record.samples for record in records),
        "total_samples": sum(
            int(split["samples"]) for split in split_records.values()
        ),
        "rows_removed_incomplete_visible_hand": sum(
            int(split["rows_removed_incomplete_visible_hand"])
            for split in split_records.values()
        ),
        "deck_signature_normalization": {
            "raw_signatures": len(
                {record.deck_signature for record in raw_records}
            ),
            "conservative_components": len(
                {record.deck_signature for record in normalized_records}
            ),
            "policy": "subset-within-two-or-overcomplete-eight-card-overlap-v1",
        },
        "splits": split_records,
        "invariants": {
            "replay_overlap": 0,
            "deck_signature_overlap": 0,
            "held_out_archetype_train_overlap": 0,
            "location_supervision_rows": 0,
            "played_card_objective": "type-head-v1",
            "noop_labels": "exact",
            "incomplete_visible_hand_rows": 0,
            "visible_hand_filter": "four-known-visible-slots-v1",
            "previous_action_chain": "previous-retained-expert-action-v1",
        },
    }
    manifest_path = output_dir / "split_manifest.json"
    atomic_write_json(manifest_path, manifest)
    manifest["manifest"] = str(manifest_path.resolve())
    manifest["manifest_sha256"] = file_sha256(manifest_path)
    return manifest


def load_raw_cascade_location_records(
    run_manifest_path: Path,
    *,
    target_games: int | None = None,
    required_label_source: str | None = None,
) -> list[LocationCorpusRecord]:
    """Load and validate published deployment-clock corpora from a raw run.

    A missing sidecar is expected when a replay contains only spells or no
    deployment clock survives the conservative agreement gate.  A published
    sidecar, however, must match its digest, contain only legal placements,
    carry complete visible hands, and retain exact replay provenance.
    """
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    complete = [
        raw for raw in run_manifest.get("records", ()) if raw.get("status") == "complete"
    ]
    if target_games is not None:
        if len(complete) < target_games:
            raise ValueError(
                f"run has only {len(complete)} complete games, expected {target_games}"
            )
        complete = complete[:target_games]

    records: list[LocationCorpusRecord] = []
    seen_replays: set[str] = set()
    for raw in complete:
        primary = Path(str(raw["corpus"])).resolve()
        game_manifest_path = primary.parent / "manifest.json"
        game_manifest = json.loads(game_manifest_path.read_text(encoding="utf-8"))
        published = game_manifest.get("location_corpus")
        if published is None:
            continue
        if not isinstance(published, dict):
            raise TypeError(f"invalid location corpus record in {game_manifest_path}")
        replay = str(game_manifest["replay"])
        if replay in seen_replays:
            raise ValueError(f"duplicate location replay {replay}")
        seen_replays.add(replay)
        corpus = primary.parent / "location_corpus.npz"
        published_path = Path(str(published["path"])).resolve()
        if published_path != corpus:
            raise ValueError(f"location corpus path mismatch for replay {replay}")
        if file_sha256(corpus) != str(published["sha256"]):
            raise ValueError(f"location corpus digest mismatch for replay {replay}")
        metadata, arrays = load_corpus(corpus)
        if (
            required_label_source is not None
            and metadata.label_source != required_label_source
        ):
            continue
        samples = int(metadata.samples)
        expected_samples = int(published["statistics"]["samples"])
        if samples <= 0 or samples != expected_samples:
            raise ValueError(f"invalid location sample count for replay {replay}")
        noop_action = int(arrays["action_masks"].shape[1] - 2)
        if bool(np.any(arrays["expert_actions"] >= noop_action)):
            raise ValueError(f"location corpus {replay} contains a non-placement label")
        target_slots = arrays["expert_actions"] // NUM_TILES
        target_tokens = arrays["hand_ids"][np.arange(samples), target_slots]
        target_cards: list[str] = []
        for token in target_tokens.tolist():
            if not 0 <= int(token) < len(metadata.token_names):
                raise ValueError(f"location corpus {replay} has an invalid target token")
            card = metadata.token_names[int(token)]
            if card.startswith("<"):
                raise ValueError(f"location corpus {replay} has an unknown target card")
            target_cards.append(card)
        for card in target_cards:
            spell = SPELL_REGISTRY.get(card)
            if spell is None:
                continue
            if (
                isinstance(spell, (ProjectileSpell, RollingProjectileSpell))
                or float(getattr(spell, "duration", 0.0) or 0.0) <= 0.0
            ):
                raise ValueError(
                    f"location corpus {replay} contains unsupported spell {card}"
                )
        sample_mask = complete_visible_hand_mask(arrays["hand_ids"])
        retained_samples = int(np.count_nonzero(sample_mask))
        if retained_samples == 0:
            continue
        with np.load(corpus, allow_pickle=False) as payload:
            required = {"source_replays", "source_frames", "source_arenas"}
            missing = required.difference(payload.files)
            if missing:
                raise ValueError(
                    f"location corpus {replay} lacks provenance {sorted(missing)}"
                )
            source_replays = payload["source_replays"].astype(str)
            source_arenas = payload["source_arenas"].astype(str)
            source_frames = payload["source_frames"].astype(np.int64)
        if source_replays.shape != (samples,) or set(source_replays.tolist()) != {
            replay
        }:
            raise ValueError(f"location replay provenance mismatch for {replay}")
        arena = str(game_manifest["arena"])
        if source_arenas.shape != (samples,) or set(source_arenas.tolist()) != {
            arena
        }:
            raise ValueError(f"location arena provenance mismatch for {replay}")
        if source_frames.shape != (samples,) or np.unique(source_frames).size != samples:
            raise ValueError(f"location frame provenance is not unique for {replay}")
        records.append(
            LocationCorpusRecord(
                replay=replay,
                arena=arena,
                corpus=corpus,
                samples=retained_samples,
                source_samples=samples,
                sample_mask=sample_mask,
                label_source=metadata.label_source,
            )
        )
    return records


def combine_raw_cascade_location_corpora(
    *,
    run_manifest_path: Path,
    output_path: Path,
    manifest_path: Path,
    seed: int,
    target_games: int | None = None,
    required_label_source: str | None = None,
) -> dict[str, Any]:
    """Combine verified clock sidecars without inventing recurrent history."""
    records = load_raw_cascade_location_records(
        run_manifest_path,
        target_games=target_games,
        required_label_source=required_label_source,
    )
    if not records:
        raise ValueError("raw cascade contains no valid location sidecars")
    manifest = combine_imitation_corpora(
        sources=[record.corpus for record in records],
        output_path=output_path,
        manifest_path=manifest_path,
        seed=seed,
        deduplicate=True,
        independent_rows=True,
        sample_masks=[record.sample_mask for record in records],
    )
    manifest.update(
        {
            "schema": "tv-royale-raw-cascade-location-clock-combined-v1",
            "source_run_manifest": str(run_manifest_path.resolve()),
            "source_run_manifest_sha256": file_sha256(run_manifest_path),
            "source_games_considered": target_games,
            "location_replays": len(records),
            "replay_ids": [record.replay for record in records],
            "sequence_contract": "independent-one-step-rows-v1",
            "required_label_source": required_label_source,
        }
    )
    atomic_write_json(manifest_path, manifest)
    return manifest


def build_raw_cascade_location_splits(
    *,
    run_manifest_path: Path,
    split_manifest_path: Path,
    output_dir: Path,
    seed: int,
    target_games: int | None = None,
    required_label_source: str | None = None,
) -> dict[str, Any]:
    """Mirror replay-disjoint type splits for sparse deployment locations."""
    records = load_raw_cascade_location_records(
        run_manifest_path,
        target_games=target_games,
        required_label_source=required_label_source,
    )
    split_manifest = json.loads(split_manifest_path.read_text(encoding="utf-8"))
    split_replays = {
        name: frozenset(str(value) for value in values.get("replay_ids", ()))
        for name, values in split_manifest.get("splits", {}).items()
    }
    reserved_replays = frozenset(
        str(value) for value in split_manifest.get("reserved_replay_ids", ())
    )
    assigned: dict[str, str] = {}
    for name, replays in split_replays.items():
        for replay in replays:
            previous = assigned.setdefault(replay, name)
            if previous != name:
                raise ValueError(
                    f"replay {replay} appears in both {previous} and {name}"
                )

    output_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[LocationCorpusRecord]] = {
        name: [] for name in split_replays
    }
    ignored: list[str] = []
    for record in records:
        split_name = assigned.get(record.replay)
        if split_name is None:
            if record.replay not in reserved_replays:
                raise ValueError(
                    f"location replay {record.replay} has no type-split assignment"
                )
            ignored.append(record.replay)
        else:
            grouped[split_name].append(record)

    published: dict[str, Any] = {}
    for name, split_records in grouped.items():
        if not split_records:
            continue
        corpus_path = output_dir / f"{name}.npz"
        corpus_manifest_path = output_dir / f"{name}_manifest.json"
        corpus_manifest = combine_imitation_corpora(
            sources=[record.corpus for record in split_records],
            output_path=corpus_path,
            manifest_path=corpus_manifest_path,
            seed=seed,
            deduplicate=True,
            independent_rows=True,
            sample_masks=[record.sample_mask for record in split_records],
        )
        published[name] = {
            "output": str(corpus_path.resolve()),
            "output_sha256": file_sha256(corpus_path),
            "samples": int(corpus_manifest["samples"]),
            "replays": len(split_records),
            "replay_ids": [record.replay for record in split_records],
            "source_samples": sum(record.samples for record in split_records),
            "unfiltered_source_samples": sum(
                record.source_samples for record in split_records
            ),
            "manifest": str(corpus_manifest_path.resolve()),
            "manifest_sha256": file_sha256(corpus_manifest_path),
            "diversity": summarize_location_corpus_diversity(corpus_path),
        }

    manifest: dict[str, Any] = {
        "schema": "tv-royale-raw-cascade-location-clock-splits-v1",
        "source_run_manifest": str(run_manifest_path.resolve()),
        "source_run_manifest_sha256": file_sha256(run_manifest_path),
        "source_split_manifest": str(split_manifest_path.resolve()),
        "source_split_manifest_sha256": file_sha256(split_manifest_path),
        "seed": seed,
        "target_games": target_games,
        "location_replays": len(records),
        "location_samples": sum(record.samples for record in records),
        "assigned_location_replays": sum(
            int(split["replays"]) for split in published.values()
        ),
        "ignored_replay_ids": sorted(ignored),
        "splits": published,
        "invariants": {
            "replay_overlap": 0,
            "follows_type_split_assignments": True,
            "ignored_replays_are_reserved_only": True,
            "independent_rows": True,
            "required_training_sequence_length": 1,
            "spell_location_policy": "persistent-area-visual-only-v1",
            "location_label_source": required_label_source,
        },
    }
    manifest_path = output_dir / "split_manifest.json"
    atomic_write_json(manifest_path, manifest)
    manifest["manifest"] = str(manifest_path.resolve())
    manifest["manifest_sha256"] = file_sha256(manifest_path)
    return manifest
