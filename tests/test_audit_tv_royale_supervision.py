from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.imitation import CorpusMetadata
from clasher.rl.oracle_corpus import file_sha256
from clasher.rl.replay_split import STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE
from scripts.audit_tv_royale_supervision import (
    EXPECTED_FOUR_WAY_SPLITS,
    SupervisionAuditError,
    audit_split_manifest,
    recover_future_confirmed_next_card_labels,
    summarize_supervision_corpus,
)


def _write_corpus(path: Path, *, label_source: str, tiles: tuple[int, ...]) -> None:
    samples = len(tiles)
    metadata = CorpusMetadata(
        schema_version=1,
        created_at="2026-08-17T00:00:00Z",
        seed=1,
        decisions=samples,
        samples=samples,
        decision_interval=1,
        max_ticks=6_000,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=1,
        token_names=("<unknown>", "Knight"),
        label_source=label_source,
    )
    action_count = NUM_HAND_SLOTS * NUM_TILES + 2
    hand_ids = np.ones((samples, 5), dtype=np.int64)
    expert_actions = np.asarray(tiles, dtype=np.int64)
    np.savez_compressed(
        path,
        entity_ids=np.zeros((samples, 1), dtype=np.int64),
        entity_features=np.zeros((samples, 1, 1), dtype=np.float32),
        entity_mask=np.ones((samples, 1), dtype=np.bool_),
        hand_ids=hand_ids,
        global_features=np.arange(samples, dtype=np.float32)[:, None],
        action_masks=np.ones((samples, action_count), dtype=np.bool_),
        previous_actions=np.full(samples, action_count - 2, dtype=np.int64),
        previous_rewards=np.zeros(samples, dtype=np.float32),
        episode_starts=np.ones(samples, dtype=np.bool_),
        expert_actions=expert_actions,
        episode_ids=np.arange(samples, dtype=np.int64),
        source_replays=np.asarray([f"replay-{index}" for index in range(samples)]),
        source_frames=np.arange(samples, dtype=np.int64),
        metadata_json=np.asarray(metadata.to_json()),
    )


def _write_manifest(
    tmp_path: Path,
    *,
    label_source: str,
    tiles: tuple[int, ...],
) -> Path:
    splits = {}
    for index, name in enumerate(EXPECTED_FOUR_WAY_SPLITS):
        corpus = tmp_path / f"{name}.npz"
        _write_corpus(corpus, label_source=label_source, tiles=tiles)
        splits[name] = {
            "output": str(corpus.resolve()),
            "output_sha256": file_sha256(corpus),
            "samples": len(tiles),
            "replay_ids": [f"{name}-replay"],
            "deck_hashes": [f"{name}-deck"],
            "archetypes": {"cycle": 1},
            "arenas": {"arena_31" if name == "chronology_test" else "arena_20": 1},
        }
    manifest = tmp_path / "split_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "chronology_min_arena": 31,
                "held_out_archetypes": ["lava-hound"],
                "splits": splits,
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_rejects_type_only_tile_zero_as_spatial_supervision(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        label_source="tv-royale-complete-hand-type-only-v2",
        tiles=(0, 0, 0),
    )

    with pytest.raises(SupervisionAuditError) as caught:
        audit_split_manifest(
            manifest,
            require_spatial=True,
            require_four_way=True,
        )

    train = caught.value.report["splits"]["train"]
    assert train["spatial"]["placeholder_tile_zero"] is True
    assert train["spatial"]["genuine_spatial_supervision"] is False
    assert train["events"]["distinct_target_cards"] == 1


def test_accepts_strict_visual_locations_and_reports_event_coverage(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(
        tmp_path,
        label_source=STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE,
        tiles=(7, 150, 511),
    )

    report = audit_split_manifest(
        manifest,
        require_spatial=True,
        require_four_way=True,
    )

    assert report["status"] == "verified"
    assert report["leakage"]["replay_overlap"] == {}
    assert report["splits"]["train"]["spatial"]["distinct_tiles"] == 3
    assert report["splits"]["train"]["events"]["source_frames"] == 3


def test_rejects_replay_leakage_before_training(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        label_source=STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE,
        tiles=(7, 150),
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["splits"]["validation"]["replay_ids"] = ["train-replay"]
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SupervisionAuditError, match="replay leakage"):
        audit_split_manifest(manifest, require_spatial=True)


def test_corpus_summary_counts_noops_separately(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.npz"
    _write_corpus(
        corpus,
        label_source=STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE,
        tiles=(7, NUM_HAND_SLOTS * NUM_TILES),
    )

    report = summarize_supervision_corpus(corpus)

    assert report["events"]["placement_or_play"] == 1
    assert report["events"]["noops"] == 1
    assert report["spatial"]["distinct_tiles"] == 1


def test_future_confirmed_next_card_requires_same_replay_and_stable_other_slots(
) -> None:
    hands = np.asarray(
        [
            [1, 2, 3, 4, 0],
            [5, 2, 3, 4, 0],  # valid refill of slot zero
            [5, 2, 3, 4, 0],
            [6, 7, 3, 4, 0],  # another slot changed, so ambiguous
            [6, 7, 3, 4, 0],
            [8, 7, 3, 4, 0],  # different replay, so forbidden lookahead
        ],
        dtype=np.int64,
    )
    actions = np.asarray([0, 0, 0, 0, 0, 0], dtype=np.int64)
    episodes = np.asarray([0, 0, 0, 0, 1, 1], dtype=np.int64)
    replays = np.asarray(["a", "a", "a", "a", "b", "c"])
    frames = np.asarray([10, 11, 12, 13, 20, 21], dtype=np.int64)

    labels, mask = recover_future_confirmed_next_card_labels(
        hand_ids=hands,
        expert_actions=actions,
        episode_ids=episodes,
        source_replays=replays,
        source_frames=frames,
    )

    assert mask.tolist() == [True, False, False, False, False, False]
    assert labels.tolist() == [5, 0, 0, 0, 0, 0]
