from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.imitation import CorpusMetadata
from clasher.rl.oracle_corpus import atomic_save_npz
from clasher.rl.replay_split import (
    STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE,
    build_raw_cascade_location_splits,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_tv_royale_raw_cascade.py"
SPEC = importlib.util.spec_from_file_location("run_tv_royale_raw_cascade", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_resumed_manifest_rate_counts_only_current_session(tmp_path: Path) -> None:
    records = [
        {"status": "complete", "replay": f"old-{index}"} for index in range(10)
    ]
    records.extend(
        {"status": "complete", "replay": f"new-{index}"} for index in range(2)
    )
    output = tmp_path / "run_manifest.json"
    args = argparse.Namespace(
        seed=1,
        target_games=20,
        max_attempts=22,
        arena_min=12,
        arena_max=31,
    )

    MODULE._write_run_manifest(
        output,
        args=args,
        queue=[],
        records=records,
        started=time.perf_counter() - 3600.0,
        initial_completed_games=10,
    )

    payload = json.loads(output.read_text())
    assert payload["completed_games"] == 12
    assert payload["session_initial_completed_games"] == 10
    assert payload["session_completed_games"] == 2
    assert 1.99 < payload["observed_completed_games_per_hour"] < 2.01


def test_resume_skips_both_completed_and_failed_replays() -> None:
    queue = [
        MODULE.ReplaySource("arena_12", replay, f"{replay}.parquet", 1, "a" * 64)
        for replay in ("complete", "failed", "new")
    ]

    pending = MODULE._pending_sources(
        queue,
        [
            {"status": "complete", "replay": "complete"},
            {"status": "failed", "replay": "failed"},
        ],
    )

    assert [source.replay for source in pending] == ["new"]


def test_completed_replays_from_manifests_builds_disjoint_wave(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.json"
    first.write_text(
        json.dumps(
            {
                "records": [
                    {"status": "complete", "replay": "used-a"},
                    {"status": "failed", "replay": "retryable"},
                ]
            }
        )
    )
    second = tmp_path / "second.json"
    second.write_text(
        json.dumps(
            {
                "records": [
                    {"status": "complete", "replay": "used-b"},
                    {"status": "complete", "replay": "used-a"},
                ]
            }
        )
    )

    excluded = MODULE.completed_replays_from_manifests(
        [str(first), str(second)]
    )

    assert excluded == {"used-a", "used-b"}


def _write_location_game(
    tmp_path: Path,
    *,
    replay: str,
    target_card: str = "Knight",
    label_source: str = STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE,
) -> tuple[Path, dict[str, object]]:
    game = tmp_path / "games" / "arena_20" / replay
    game.mkdir(parents=True)
    samples = 2
    noop = 4 * 576
    masks = np.ones((samples, noop + 2), dtype=np.bool_)
    metadata = CorpusMetadata(
        schema_version=1,
        created_at="2026-08-12T00:00:00Z",
        seed=1,
        decisions=samples,
        samples=samples,
        decision_interval=1,
        max_ticks=3000,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=2,
        token_names=("<pad>", "<unknown>", target_card),
        label_source=label_source,
    )
    payload = {
        "entity_ids": np.zeros((samples, 2), dtype=np.int64),
        "entity_features": np.zeros((samples, 2, 32), dtype=np.float32),
        "entity_mask": np.zeros((samples, 2), dtype=np.bool_),
        "hand_ids": np.full((samples, 5), 2, dtype=np.int64),
        "global_features": np.zeros((samples, 18), dtype=np.float32),
        "action_masks": masks,
        "previous_actions": np.asarray([noop, 3], dtype=np.int64),
        "previous_rewards": np.zeros(samples, dtype=np.float32),
        "episode_starts": np.asarray([True, False]),
        "expert_actions": np.asarray([3, 7], dtype=np.int64),
        "episode_ids": np.zeros(samples, dtype=np.int64),
        "source_replays": np.asarray([replay, replay]),
        "source_frames": np.asarray([5, 9], dtype=np.int64),
        "source_indices": np.asarray([5, 9], dtype=np.int64),
        "source_arenas": np.asarray(["arena_20", "arena_20"]),
        "metadata_json": np.asarray(metadata.to_json()),
    }
    location = game / "location_corpus.npz"
    atomic_save_npz(location, payload)
    digest = hashlib.sha256(location.read_bytes()).hexdigest()
    primary = game / "corpus.npz"
    atomic_save_npz(primary, payload)
    manifest = {
        "arena": "arena_20",
        "replay": replay,
        "corpus": {"path": str(primary), "sha256": hashlib.sha256(primary.read_bytes()).hexdigest()},
        "location_corpus": {
            "path": str(location),
            "sha256": digest,
            "statistics": {"samples": samples},
        },
    }
    (game / "manifest.json").write_text(json.dumps(manifest))
    return primary, manifest


def test_combined_publisher_includes_validated_location_sidecar(
    tmp_path: Path,
) -> None:
    primary, _ = _write_location_game(tmp_path, replay="r1")
    run_manifest = tmp_path / "run_manifest.json"
    records = [{"status": "complete", "corpus": str(primary), "replay": "r1"}]
    run_manifest.write_text(json.dumps({"records": records}))
    args = argparse.Namespace(target_games=1, seed=17)

    published = MODULE._publish_combined_corpora(
        args=args,
        output_root=tmp_path,
        run_manifest_path=run_manifest,
        records=records,
    )

    assert published["location_samples"] == 2
    assert Path(str(published["location_combined"])).is_file()
    with np.load(str(published["location_combined"]), allow_pickle=False) as data:
        assert data["episode_starts"].tolist() == [True, True]
        assert data["previous_actions"].tolist() == [4 * 576, 4 * 576]


def test_combined_public_state_v2_follows_deduplicated_corpus_order(
    tmp_path: Path,
) -> None:
    primary, _ = _write_location_game(tmp_path, replay="r1")
    with np.load(primary, allow_pickle=False) as corpus:
        public = {
            "entity_ids": corpus["entity_ids"].copy(),
            "entity_features": corpus["entity_features"].copy(),
            "entity_mask": np.ones_like(corpus["entity_mask"]),
            "entity_id_confidence": np.asarray(
                [[0.2, 0.2], [0.8, 0.8]], dtype=np.float16
            ),
            "entity_feature_confidence": np.ones_like(
                corpus["entity_features"], dtype=np.float16
            ),
            "hand_ids": corpus["hand_ids"].copy(),
            "hand_id_confidence": np.ones_like(
                corpus["hand_ids"], dtype=np.float16
            ),
            "global_features": corpus["global_features"].copy(),
            "global_feature_confidence": np.ones_like(
                corpus["global_features"], dtype=np.float16
            ),
            "opponent_history_ids": np.zeros((2, 0), dtype=np.int64),
            "opponent_history_ages": np.zeros((2, 0), dtype=np.float32),
            "opponent_history_confidence": np.zeros((2, 0), dtype=np.float16),
            "opponent_seen_card_ids": np.zeros((2, 0), dtype=np.int64),
            "opponent_seen_card_confidence": np.zeros((2, 0), dtype=np.float16),
            "source_indices": corpus["source_indices"].copy(),
            "source_frames": corpus["source_frames"].copy(),
            "expert_actions": corpus["expert_actions"].copy(),
            "schema_version": np.asarray(2),
        }
        reversed_corpus = {
            name: corpus[name][::-1].copy()
            for name in corpus.files
            if name
            not in {
                "metadata_json",
                "source_replays",
                "source_indices",
                "source_frames",
                "source_arenas",
            }
        }
        reversed_corpus["metadata_json"] = corpus["metadata_json"].copy()
    public_path = tmp_path / "public_state_v2.npz"
    combined_path = tmp_path / "combined.npz"
    atomic_save_npz(public_path, public)
    atomic_save_npz(combined_path, reversed_corpus)
    output = tmp_path / "combined_public_v2.npz"
    manifest = tmp_path / "combined_public_v2.json"

    result = MODULE._combine_public_state_v2(
        records=[{"corpus": str(primary), "public_state_v2": str(public_path)}],
        combined_corpus_path=combined_path,
        output_path=output,
        manifest_path=manifest,
    )

    assert result["samples"] == 2
    assert result["source_games"] == 1
    with np.load(output, allow_pickle=False) as combined_public:
        assert combined_public["source_frames"].tolist() == [9, 5]
        np.testing.assert_allclose(
            combined_public["entity_id_confidence"][:, 0],
            np.asarray([0.8, 0.2]),
            rtol=0,
            atol=1e-3,
        )


def test_game_validation_reads_public_provenance_from_full_corpus(
    tmp_path: Path,
) -> None:
    primary, manifest = _write_location_game(tmp_path, replay="r1")
    with np.load(primary, allow_pickle=False) as corpus:
        public = {
            "schema_version": np.asarray(2),
            "expert_actions": corpus["expert_actions"].copy(),
            "source_indices": corpus["source_indices"].copy(),
            "source_frames": corpus["source_frames"].copy(),
        }
    public_path = primary.parent / "public_state_v2.npz"
    atomic_save_npz(public_path, public)
    manifest["public_state_v2"] = {
        "path": str(public_path),
        "sha256": hashlib.sha256(public_path.read_bytes()).hexdigest(),
    }
    (primary.parent / "manifest.json").write_text(json.dumps(manifest))
    source = MODULE.ReplaySource(
        arena="arena_20",
        replay="r1",
        repo_path="arena_20/r1/frames.parquet",
        size=1,
        sha256="a" * 64,
    )

    validated, _ = MODULE._validated_game_result(tmp_path, source)

    assert validated == primary


def test_location_split_follows_existing_replay_assignment(tmp_path: Path) -> None:
    primary, _ = _write_location_game(tmp_path, replay="r1")
    run_manifest = tmp_path / "run_manifest.json"
    run_manifest.write_text(
        json.dumps(
            {
                "records": [
                    {"status": "complete", "corpus": str(primary), "replay": "r1"}
                ]
            }
        )
    )
    split_manifest = tmp_path / "type_split.json"
    split_manifest.write_text(
        json.dumps({"splits": {"train": {"replay_ids": ["r1"]}}})
    )

    result = build_raw_cascade_location_splits(
        run_manifest_path=run_manifest,
        split_manifest_path=split_manifest,
        output_dir=tmp_path / "location_split",
        seed=19,
        target_games=1,
        required_label_source=STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE,
    )

    assert result["invariants"]["replay_overlap"] == 0
    assert result["invariants"]["ignored_replays_are_reserved_only"] is True
    assert (
        result["invariants"]["spell_location_policy"]
        == "persistent-area-visual-only-v1"
    )
    assert result["splits"]["train"]["replay_ids"] == ["r1"]
    assert result["splits"]["train"]["samples"] == 2
    assert result["splits"]["train"]["diversity"] == {
        "samples": 2,
        "distinct_target_cards": 1,
        "target_card_counts": {"Knight": 2},
        "distinct_target_tiles": 2,
        "distinct_coarse_regions_3x4": 2,
        "covered_x_columns": 2,
        "covered_y_rows": 1,
        "covered_y_bands_4_rows": 1,
        "left_samples": 2,
        "right_samples": 0,
        "minority_side_fraction": 0.0,
        "persistent_area_spell_cards": [],
        "persistent_area_spell_samples": 0,
    }


def test_location_split_excludes_pre_strict_contract_sidecars(tmp_path: Path) -> None:
    primary, _ = _write_location_game(
        tmp_path,
        replay="legacy",
        label_source="tv-royale-raw-cascade-location-visual-v2",
    )
    run_manifest = tmp_path / "run_manifest.json"
    run_manifest.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "status": "complete",
                        "corpus": str(primary),
                        "replay": "legacy",
                    }
                ]
            }
        )
    )
    split_manifest = tmp_path / "type_split.json"
    split_manifest.write_text(
        json.dumps({"splits": {"train": {"replay_ids": ["legacy"]}}})
    )

    result = build_raw_cascade_location_splits(
        run_manifest_path=run_manifest,
        split_manifest_path=split_manifest,
        output_dir=tmp_path / "location_split",
        seed=19,
        target_games=1,
        required_label_source=STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE,
    )

    assert result["location_replays"] == 0
    assert result["location_samples"] == 0
    assert result["splits"] == {}
    assert (
        result["invariants"]["location_label_source"]
        == STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE
    )


def test_location_loader_rejects_projectile_spell_labels(tmp_path: Path) -> None:
    primary, _ = _write_location_game(tmp_path, replay="r1", target_card="Fireball")
    run_manifest = tmp_path / "run_manifest.json"
    run_manifest.write_text(
        json.dumps(
            {
                "records": [
                    {"status": "complete", "corpus": str(primary), "replay": "r1"}
                ]
            }
        )
    )

    with pytest.raises(ValueError, match="unsupported spell Fireball"):
        build_raw_cascade_location_splits(
            run_manifest_path=run_manifest,
            split_manifest_path=tmp_path / "missing.json",
            output_dir=tmp_path / "location_split",
            seed=19,
            target_games=1,
        )
