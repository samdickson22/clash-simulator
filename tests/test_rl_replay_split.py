import json
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.replay_split import (
    ReplaySplitRecord,
    assign_replay_splits,
    complete_visible_hand_mask,
    exclude_reserved_replays,
    first_completed_replay_ids,
    normalize_noisy_deck_signatures,
    rechain_previous_actions,
)


def test_complete_visible_hand_filter_ignores_only_unknown_next_card() -> None:
    hand_ids = np.asarray(
        [
            [2, 3, 4, 5, 0],
            [2, 0, 4, 5, 6],
            [0, 3, 4, 5, 6],
        ],
        dtype=np.int64,
    )

    assert complete_visible_hand_mask(hand_ids).tolist() == [True, False, False]
    with pytest.raises(ValueError, match="at least four"):
        complete_visible_hand_mask(np.zeros((2, 3), dtype=np.int64))


def test_filtered_episode_previous_actions_are_rechained() -> None:
    noop = 4 * 576
    expert = np.asarray([17, noop, 42], dtype=np.int64)

    assert rechain_previous_actions(expert).tolist() == [noop, 17, noop]
    with pytest.raises(ValueError, match="non-empty"):
        rechain_previous_actions(np.asarray([], dtype=np.int64))


def _record(
    replay: str,
    *,
    arena: int,
    deck: tuple[str, ...],
    archetype: str,
) -> ReplaySplitRecord:
    return ReplaySplitRecord(
        replay=replay,
        arena=f"arena_{arena}",
        arena_number=arena,
        corpus=Path(f"{replay}.npz"),
        deck_signature=deck,
        enabled_cards=(),
        archetype=archetype,
        samples=10,
        plays=6,
        noops=4,
    )


def test_split_keeps_replays_decks_archetypes_and_chronology_disjoint() -> None:
    records = [
        _record("hog-a1", arena=20, deck=("hog-a",), archetype="hog"),
        _record("hog-a2", arena=21, deck=("hog-a",), archetype="hog"),
        _record("hog-b", arena=22, deck=("hog-b",), archetype="hog"),
        _record("hog-c", arena=23, deck=("hog-c",), archetype="hog"),
        _record("giant-a", arena=24, deck=("giant-a",), archetype="giant"),
        _record("giant-b", arena=25, deck=("giant-b",), archetype="giant"),
        _record("latest", arena=31, deck=("latest",), archetype="hog"),
        _record("latest-copy", arena=19, deck=("latest",), archetype="hog"),
        _record("graveyard", arena=20, deck=("graveyard",), archetype="graveyard"),
    ]
    splits = assign_replay_splits(
        records,
        seed=17,
        validation_fraction=0.34,
        held_out_archetypes=frozenset({"graveyard"}),
        chronology_min_arena=31,
    )

    assert {record.replay for record in splits["archetype_test"]} == {"graveyard"}
    assert {record.replay for record in splits["chronology_test"]} == {
        "latest",
        "latest-copy",
    }
    assert splits["train"]
    assert splits["validation"]
    split_decks = [
        {record.deck_signature for record in split} for split in splits.values()
    ]
    for index, left in enumerate(split_decks):
        for right in split_decks[index + 1 :]:
            assert left.isdisjoint(right)


def test_split_is_deterministic() -> None:
    records = [
        _record(f"r{index}", arena=20, deck=(f"d{index}",), archetype="hog")
        for index in range(12)
    ]
    first = assign_replay_splits(records, seed=91, validation_fraction=0.25)
    second = assign_replay_splits(records, seed=91, validation_fraction=0.25)
    assert first == second


def test_split_without_whole_archetype_holdouts_distributes_each_archetype() -> None:
    records = [
        _record(
            f"{archetype}-{index}",
            arena=20,
            deck=(f"{archetype}-deck-{index}",),
            archetype=archetype,
        )
        for archetype in ("graveyard", "x-bow")
        for index in range(4)
    ]

    splits = assign_replay_splits(
        records,
        seed=91,
        validation_fraction=0.25,
        held_out_archetypes=frozenset(),
    )

    assert not splits["archetype_test"]
    assert {record.archetype for record in splits["train"]} == {
        "graveyard",
        "x-bow",
    }
    assert {record.archetype for record in splits["validation"]} == {
        "graveyard",
        "x-bow",
    }


def test_split_groups_partial_signature_with_complete_chronology_deck() -> None:
    base = tuple(f"card-{index}" for index in range(8))
    records = [
        _record("partial", arena=20, deck=base[:-1], archetype="hog"),
        _record("complete", arena=31, deck=base, archetype="hog"),
        _record("other-a", arena=20, deck=("other-a",), archetype="hog"),
        _record("other-b", arena=20, deck=("other-b",), archetype="hog"),
    ]

    splits = assign_replay_splits(
        records,
        seed=17,
        validation_fraction=0.25,
        chronology_min_arena=31,
    )

    assert {record.replay for record in splits["chronology_test"]} == {
        "partial",
        "complete",
    }


def test_signature_normalization_keeps_real_eight_card_variants_distinct() -> None:
    common = tuple(f"card-{index}" for index in range(7))
    first = _record("first", arena=20, deck=common + ("spell-a",), archetype="hog")
    second = _record(
        "second", arena=20, deck=common + ("spell-b",), archetype="hog"
    )

    normalized = normalize_noisy_deck_signatures((first, second))

    assert normalized[0].deck_signature != normalized[1].deck_signature


def test_signature_normalization_groups_two_overcomplete_observations() -> None:
    common = tuple(f"card-{index}" for index in range(8))
    first = _record("first", arena=20, deck=common + ("noise-a",), archetype="hog")
    second = _record(
        "second", arena=20, deck=common + ("noise-b",), archetype="hog"
    )

    normalized = normalize_noisy_deck_signatures((first, second))

    assert normalized[0].deck_signature == normalized[1].deck_signature


def test_final_evaluation_replays_are_removed_exactly() -> None:
    records = (
        _record("train", arena=20, deck=("train",), archetype="hog"),
        _record("final", arena=20, deck=("final",), archetype="hog"),
    )

    filtered = exclude_reserved_replays(records, frozenset({"final"}))

    assert [record.replay for record in filtered] == ["train"]
    with pytest.raises(ValueError, match="absent from the source"):
        exclude_reserved_replays(records, frozenset({"missing"}))


def test_first_completed_replay_ids_uses_completed_chronology(tmp_path: Path) -> None:
    manifest = tmp_path / "run_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "records": [
                    {"status": "complete", "replay": "first"},
                    {"status": "failed", "replay": "ignored"},
                    {"status": "complete", "replay": "second"},
                    {"status": "complete", "replay": "third"},
                ]
            }
        )
    )

    assert first_completed_replay_ids(manifest, 2) == frozenset({"first", "second"})
    assert first_completed_replay_ids(manifest, 0) == frozenset()
    with pytest.raises(ValueError, match="only 3 completed"):
        first_completed_replay_ids(manifest, 4)
    with pytest.raises(ValueError, match="non-negative"):
        first_completed_replay_ids(manifest, -1)
