from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .data import CardDataLoader
from .paths import decks_path as resolve_decks_path

InteractionKind = Literal["1v1", "2v2"]
GeometryName = Literal[
    "center",
    "left_lane",
    "right_lane",
    "river_left",
    "river_right",
    "split_lane",
]
EventFamily = Literal[
    "ordinary",
    "target_order",
    "simultaneous_attack",
    "simultaneous_death",
    "stun",
    "slow",
    "rage",
    "death_payload",
    "projectile",
    "retarget",
    "allied_collision",
]


GEOMETRIES: tuple[GeometryName, ...] = (
    "center",
    "left_lane",
    "right_lane",
    "river_left",
    "river_right",
    "split_lane",
)
EVENT_FAMILIES: tuple[EventFamily, ...] = (
    "ordinary",
    "target_order",
    "simultaneous_attack",
    "simultaneous_death",
    "stun",
    "slow",
    "rage",
    "death_payload",
    "projectile",
    "retarget",
    "allied_collision",
)


@dataclass(frozen=True)
class InteractionCase:
    index: int
    kind: InteractionKind
    team_0: tuple[str, ...]
    team_1: tuple[str, ...]
    fast_path: bool
    mirrored: bool
    geometry: GeometryName
    team_0_spawn_reversed: bool
    team_1_spawn_reversed: bool
    event_family: EventFamily

    @property
    def case_id(self) -> str:
        return f"{self.kind}-{self.index:07d}"

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["case_id"] = self.case_id
        return payload


@dataclass(frozen=True)
class ShardRange:
    shard_index: int
    shard_count: int
    start: int
    stop: int

    @property
    def size(self) -> int:
        return self.stop - self.start


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def enabled_troop_cards(
    decks_path: str | Path = "decks.json",
    *,
    loader: CardDataLoader | None = None,
) -> tuple[str, ...]:
    """Return every enabled deployable character, including Champions.

    The matrix is driven by the enabled deck file and normalized card kind;
    no card-name allowlist is maintained here.
    """

    resolved = resolve_decks_path(decks_path, must_exist=True)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    enabled_names = {
        str(card)
        for deck in payload.get("decks", [])
        for card in deck.get("cards", [])
    }
    card_loader = CardDataLoader() if loader is None else loader
    troops: list[str] = []
    missing: list[str] = []
    for name in sorted(enabled_names):
        definition = card_loader.get_card_definition(name)
        if definition is None:
            missing.append(name)
            continue
        if definition.kind in {"troop", "champion"}:
            troops.append(name)
    if missing:
        raise ValueError(f"enabled cards missing definitions: {missing}")
    if not troops:
        raise ValueError(f"no enabled troop cards in {resolved}")
    return tuple(troops)


def one_v_one_case_count(card_count: int) -> int:
    if card_count < 0:
        raise ValueError("card_count must be non-negative")
    # Ordered card roles, two position mirrors, and scalar/fast engines.
    return card_count * card_count * 2 * 2


def team_composition_count(card_count: int) -> int:
    if card_count < 0:
        raise ValueError("card_count must be non-negative")
    return card_count * (card_count + 1) // 2


def two_v_two_composition_count(card_count: int) -> int:
    team_count = team_composition_count(card_count)
    # Team order is canonical: swapping the two complete teams does not create
    # a second base composition. Mirroring and spawn order are systematic axes.
    return team_count * (team_count + 1) // 2


def shard_range(total: int, shard_index: int, shard_count: int) -> ShardRange:
    if total < 0:
        raise ValueError("total must be non-negative")
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must be in [0, shard_count)")
    return ShardRange(
        shard_index=shard_index,
        shard_count=shard_count,
        start=total * shard_index // shard_count,
        stop=total * (shard_index + 1) // shard_count,
    )


def _one_v_one_case(cards: Sequence[str], index: int) -> InteractionCase:
    total = one_v_one_case_count(len(cards))
    if not 0 <= index < total:
        raise IndexError(index)
    card_count = len(cards)
    card_pair_index, axis_index = divmod(index, 4)
    first_index, second_index = divmod(card_pair_index, card_count)
    return InteractionCase(
        index=index,
        kind="1v1",
        team_0=(cards[first_index],),
        team_1=(cards[second_index],),
        fast_path=bool(axis_index & 1),
        mirrored=bool(axis_index & 2),
        geometry="center",
        team_0_spawn_reversed=False,
        team_1_spawn_reversed=False,
        event_family="ordinary",
    )


def iter_one_v_one_cases(
    cards: Sequence[str],
    *,
    shard_index: int = 0,
    shard_count: int = 1,
) -> Iterator[InteractionCase]:
    selected = shard_range(
        one_v_one_case_count(len(cards)),
        shard_index,
        shard_count,
    )
    for index in range(selected.start, selected.stop):
        yield _one_v_one_case(cards, index)


def _team_compositions(cards: Sequence[str]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (cards[first], cards[second])
        for first in range(len(cards))
        for second in range(first, len(cards))
    )


def _unordered_pair_row_starts(item_count: int) -> tuple[int, ...]:
    starts = [0]
    for first in range(item_count):
        starts.append(starts[-1] + item_count - first)
    return tuple(starts)


def _unordered_pair_at(item_count: int, index: int) -> tuple[int, int]:
    total = item_count * (item_count + 1) // 2
    if not 0 <= index < total:
        raise IndexError(index)
    starts = _unordered_pair_row_starts(item_count)
    first = bisect_right(starts, index) - 1
    second = first + index - starts[first]
    return first, second


def _systematic_axes(index: int) -> tuple[
    bool,
    bool,
    GeometryName,
    bool,
    bool,
    EventFamily,
]:
    # Independent coprime-ish strides spread each declared axis across the
    # exhaustive base-composition catalog without claiming the Cartesian
    # product of all axes is exhaustive.
    return (
        bool(index % 2),
        bool((index // 2) % 2),
        GEOMETRIES[(index * 5 + index // 7) % len(GEOMETRIES)],
        bool((index // 4) % 2),
        bool((index // 8) % 2),
        EVENT_FAMILIES[(index * 7 + index // 13) % len(EVENT_FAMILIES)],
    )


def _two_v_two_case(cards: Sequence[str], index: int) -> InteractionCase:
    compositions = _team_compositions(cards)
    first, second = _unordered_pair_at(len(compositions), index)
    (
        fast_path,
        mirrored,
        geometry,
        reverse_0,
        reverse_1,
        event_family,
    ) = _systematic_axes(index)
    return InteractionCase(
        index=index,
        kind="2v2",
        team_0=compositions[first],
        team_1=compositions[second],
        fast_path=fast_path,
        mirrored=mirrored,
        geometry=geometry,
        team_0_spawn_reversed=reverse_0,
        team_1_spawn_reversed=reverse_1,
        event_family=event_family,
    )


def iter_two_v_two_cases(
    cards: Sequence[str],
    *,
    shard_index: int = 0,
    shard_count: int = 1,
) -> Iterator[InteractionCase]:
    selected = shard_range(
        two_v_two_composition_count(len(cards)),
        shard_index,
        shard_count,
    )
    for index in range(selected.start, selected.stop):
        yield _two_v_two_case(cards, index)


def matrix_manifest(
    decks_path: str | Path = "decks.json",
    *,
    one_v_one_shards: int = 32,
    two_v_two_shards: int = 256,
) -> dict[str, object]:
    resolved_decks = resolve_decks_path(decks_path, must_exist=True)
    loader = CardDataLoader()
    cards = enabled_troop_cards(resolved_decks, loader=loader)
    data_path = loader.data_file
    one_count = one_v_one_case_count(len(cards))
    two_count = two_v_two_composition_count(len(cards))
    return {
        "schema_version": 1,
        "enabled_troop_cards": list(cards),
        "enabled_troop_count": len(cards),
        "decks": {
            "path_name": resolved_decks.name,
            "sha256": _sha256_file(resolved_decks),
        },
        "gamedata": {
            "path_name": data_path.name,
            "sha256": _sha256_file(data_path),
        },
        "one_v_one": {
            "coverage": "exhaustive ordered cards x mirrored positions x scalar/fast",
            "case_count": one_count,
            "shard_count": one_v_one_shards,
            "shards": [
                asdict(shard_range(one_count, index, one_v_one_shards))
                for index in range(one_v_one_shards)
            ],
        },
        "two_v_two": {
            "coverage": "exhaustive unordered team-composition matchups",
            "case_count": two_count,
            "team_composition_count": team_composition_count(len(cards)),
            "systematic_not_exhaustive_axes": {
                "fast_path": [False, True],
                "mirrored": [False, True],
                "geometry": list(GEOMETRIES),
                "team_spawn_reversed": [False, True],
                "event_family": list(EVENT_FAMILIES),
            },
            "shard_count": two_v_two_shards,
            "shards": [
                asdict(shard_range(two_count, index, two_v_two_shards))
                for index in range(two_v_two_shards)
            ],
        },
    }
