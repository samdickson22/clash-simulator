from pathlib import Path

import numpy as np
import pytest
import torch

from clasher.rl.imitation import CorpusMetadata, load_corpus
from clasher.rl.imitation_mix import (
    combine_imitation_corpora,
    merge_provenance_corpora,
    split_provenance_corpora,
)
from clasher.rl.oracle_corpus import atomic_save_npz
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import PlacementRehearsal


def _write_corpus(
    path: Path,
    *,
    episode_ids: list[int],
    marker: float,
    decision_interval: int = 4,
) -> None:
    samples = len(episode_ids)
    actions = np.arange(samples, dtype=np.int64) % 3
    masks = np.ones((samples, 4), dtype=np.bool_)
    metadata = CorpusMetadata(
        schema_version=1,
        created_at="2026-08-10T00:00:00Z",
        seed=1,
        decisions=samples,
        samples=samples,
        decision_interval=decision_interval,
        max_ticks=20,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=2,
        token_names=("<pad>", "<unknown>"),
        label_source="behavior",
    )
    atomic_save_npz(
        path,
        {
            "entity_ids": np.zeros((samples, 2), dtype=np.int64),
            "entity_features": np.full((samples, 2, 32), marker, dtype=np.float32),
            "entity_mask": np.zeros((samples, 2), dtype=np.bool_),
            "hand_ids": np.zeros((samples, 5), dtype=np.int64),
            "global_features": np.zeros((samples, 18), dtype=np.float32),
            "action_masks": masks,
            "previous_actions": np.zeros(samples, dtype=np.int64),
            "previous_rewards": np.zeros(samples, dtype=np.float64),
            "episode_starts": np.asarray(
                [
                    index == 0 or episode_ids[index - 1] != episode
                    for index, episode in enumerate(episode_ids)
                ],
                dtype=np.bool_,
            ),
            "expert_actions": actions,
            "episode_ids": np.asarray(episode_ids, dtype=np.int64),
            "metadata_json": np.asarray(metadata.to_json()),
        },
    )


def test_combiner_samples_complete_episodes_and_renumbers(tmp_path: Path) -> None:
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    output = tmp_path / "mixed.npz"
    manifest = tmp_path / "mixed.json"
    _write_corpus(first, episode_ids=[0, 0, 1, 1, 1], marker=1.0)
    _write_corpus(second, episode_ids=[4, 4, 5, 5], marker=2.0)

    result = combine_imitation_corpora(
        sources=[first, second],
        output_path=output,
        manifest_path=manifest,
        seed=7,
        target_samples=[2, None],
    )

    metadata, arrays = load_corpus(output)
    assert result["samples"] in (6, 7)
    assert metadata.label_source == "mixed-rehearsal"
    assert arrays["entity_features"].dtype == np.float16
    assert np.array_equal(np.unique(arrays["episode_ids"]), np.arange(3))
    assert arrays["episode_ids"][-4:].tolist() == [1, 1, 2, 2]
    assert manifest.is_file()

    builder = StructuredObservationBuilder(
        decks_path="decks.json",
        max_entities=2,
        token_names=("<pad>", "<unknown>"),
    )
    rehearsal = PlacementRehearsal.load(
        output,
        builder=builder,
        device=torch.device("cpu"),
        sequence_length=1,
        seed=11,
        loss_component="location",
    )
    assert len(rehearsal.chunks) == result["samples"]
    assert rehearsal.loss_component == "location"


def test_combiner_explicitly_records_mixed_decision_intervals(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    output = tmp_path / "mixed.npz"
    manifest = tmp_path / "mixed.json"
    _write_corpus(
        first,
        episode_ids=[0, 0],
        marker=1.0,
        decision_interval=1,
    )
    _write_corpus(
        second,
        episode_ids=[4, 4],
        marker=2.0,
        decision_interval=4,
    )

    result = combine_imitation_corpora(
        sources=[first, second],
        output_path=output,
        manifest_path=manifest,
        seed=8,
        allow_mixed_decision_intervals=True,
    )

    metadata, _ = load_corpus(output)
    assert metadata.decision_interval == 0
    assert result["allow_mixed_decision_intervals"] is True
    assert [source["decision_interval"] for source in result["sources"]] == [1, 4]


def test_type_rehearsal_accepts_explicit_noop_only_sequences(tmp_path: Path) -> None:
    source = tmp_path / "noop.npz"
    samples = 4
    action_count = 4 * 18 * 32 + 2
    noop_action = action_count - 2
    metadata = CorpusMetadata(
        schema_version=1,
        created_at="2026-08-11T00:00:00Z",
        seed=2,
        decisions=samples,
        samples=samples,
        decision_interval=1,
        max_ticks=20,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=2,
        token_names=("<pad>", "<unknown>"),
        label_source="human-noop",
    )
    action_masks = np.zeros((samples, action_count), dtype=np.bool_)
    action_masks[:, :2] = True
    action_masks[:, noop_action] = True
    atomic_save_npz(
        source,
        {
            "entity_ids": np.zeros((samples, 2), dtype=np.int64),
            "entity_features": np.zeros((samples, 2, 32), dtype=np.float32),
            "entity_mask": np.zeros((samples, 2), dtype=np.bool_),
            "hand_ids": np.zeros((samples, 5), dtype=np.int64),
            "global_features": np.zeros((samples, 18), dtype=np.float32),
            "action_masks": action_masks,
            "previous_actions": np.full(samples, noop_action, dtype=np.int64),
            "previous_rewards": np.zeros(samples, dtype=np.float32),
            "episode_starts": np.asarray([True, False, False, False]),
            "expert_actions": np.full(samples, noop_action, dtype=np.int64),
            "episode_ids": np.zeros(samples, dtype=np.int64),
            "metadata_json": np.asarray(metadata.to_json()),
        },
    )
    builder = StructuredObservationBuilder(
        decks_path="decks.json",
        max_entities=2,
        token_names=("<pad>", "<unknown>"),
    )

    rehearsal = PlacementRehearsal.load(
        source,
        builder=builder,
        device=torch.device("cpu"),
        sequence_length=4,
        seed=12,
        loss_component="type",
    )

    assert rehearsal.chunks.tolist() == [[0, 1, 2, 3]]
    assert rehearsal.loss_component == "type"


def test_combiner_deduplicates_exact_rows_and_repairs_sequence_context(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    output = tmp_path / "mixed.npz"
    manifest = tmp_path / "mixed.json"
    _write_corpus(first, episode_ids=[0, 0], marker=1.0)
    _write_corpus(second, episode_ids=[4, 4, 5], marker=1.0)

    result = combine_imitation_corpora(
        sources=[first, second],
        output_path=output,
        manifest_path=manifest,
        seed=13,
    )

    _, arrays = load_corpus(output)
    assert result["samples"] == 3
    assert result["episodes"] == 2
    assert result["sources"][1]["duplicate_samples_removed"] == 2
    assert result["sources"][1]["duplicate_episodes_removed"] == 1
    assert arrays["episode_ids"].tolist() == [0, 0, 1]
    assert arrays["episode_starts"].tolist() == [True, False, True]
    assert arrays["previous_actions"].tolist() == [2, 0, 2]


def test_combiner_preserves_behavior_history_when_expert_labels_differ(
    tmp_path: Path,
) -> None:
    source = tmp_path / "dagger.npz"
    output = tmp_path / "mixed.npz"
    manifest = tmp_path / "mixed.json"
    _write_corpus(source, episode_ids=[0, 0, 0], marker=1.0)
    with np.load(source, allow_pickle=False) as stored:
        payload = {name: stored[name].copy() for name in stored.files}
    # State rows 1 and 2 were reached after behavior actions 2 and 2, while
    # their preceding oracle labels are 0 and 1.  Replacing this history with
    # expert labels would make the recurrent input inconsistent with the state.
    payload["previous_actions"] = np.asarray([2, 2, 2], dtype=np.int64)
    payload["expert_actions"] = np.asarray([0, 1, 2], dtype=np.int64)
    atomic_save_npz(source, payload)

    result = combine_imitation_corpora(
        sources=[source],
        output_path=output,
        manifest_path=manifest,
        seed=29,
        deduplicate=False,
    )

    _, arrays = load_corpus(output)
    assert arrays["episode_starts"].tolist() == [True, False, False]
    assert arrays["previous_actions"].tolist() == [2, 2, 2]
    assert result["previous_action_policy"] == "preserve-source-behavior"


def test_combiner_can_make_sparse_labels_independent_rows(tmp_path: Path) -> None:
    source = tmp_path / "sparse.npz"
    output = tmp_path / "independent.npz"
    manifest = tmp_path / "independent.json"
    _write_corpus(source, episode_ids=[0, 0, 0], marker=1.0)

    result = combine_imitation_corpora(
        sources=[source],
        output_path=output,
        manifest_path=manifest,
        seed=13,
        independent_rows=True,
    )

    _, arrays = load_corpus(output)
    assert result["independent_rows"] is True
    assert result["episodes"] == 3
    assert arrays["episode_ids"].tolist() == [0, 1, 2]
    assert arrays["episode_starts"].tolist() == [True, True, True]
    assert arrays["previous_actions"].tolist() == [2, 2, 2]
    assert arrays["previous_rewards"].tolist() == [0.0, 0.0, 0.0]


def test_independent_row_combiner_can_filter_untrusted_samples(tmp_path: Path) -> None:
    source = tmp_path / "sparse.npz"
    output = tmp_path / "filtered.npz"
    manifest = tmp_path / "filtered.json"
    _write_corpus(source, episode_ids=[0, 0, 0], marker=1.0)

    result = combine_imitation_corpora(
        sources=[source],
        output_path=output,
        manifest_path=manifest,
        seed=13,
        independent_rows=True,
        sample_masks=[np.asarray([True, False, True])],
    )

    _, arrays = load_corpus(output)
    assert result["samples"] == 2
    assert result["sources"][0]["filtered_samples_removed"] == 1
    assert arrays["expert_actions"].tolist() == [0, 2]


def test_sample_masks_require_independent_rows(tmp_path: Path) -> None:
    source = tmp_path / "source.npz"
    _write_corpus(source, episode_ids=[0], marker=1.0)
    with pytest.raises(ValueError, match="independent_rows"):
        combine_imitation_corpora(
            sources=[source],
            output_path=tmp_path / "bad.npz",
            manifest_path=tmp_path / "bad.json",
            seed=1,
            sample_masks=[np.asarray([True])],
        )


def test_provenance_merge_builds_mixed_chronological_sequences(
    tmp_path: Path,
) -> None:
    deployments = tmp_path / "deployments.npz"
    waits = tmp_path / "waits.npz"
    output = tmp_path / "chronological.npz"
    manifest = tmp_path / "chronological.json"
    _write_corpus(deployments, episode_ids=[0, 0, 1], marker=1.0)
    _write_corpus(waits, episode_ids=[3, 3, 4], marker=2.0)
    for path, replays, frames in (
        (deployments, ["shared", "shared", "deploy-only"], [20, 40, 10]),
        (waits, ["shared", "shared", "wait-only"], [10, 30, 10]),
    ):
        with np.load(path, allow_pickle=False) as stored:
            payload = {name: stored[name].copy() for name in stored.files}
        if path == waits:
            payload["expert_actions"] = np.full(3, 2, dtype=np.int64)
        payload.update(
            {
                "source_replays": np.asarray(replays),
                "source_frames": np.asarray(frames, dtype=np.int64),
                "source_arenas": np.asarray(["arena_28"] * 3),
            }
        )
        atomic_save_npz(path, payload)

    result = merge_provenance_corpora(
        sources=[deployments, waits],
        output_path=output,
        manifest_path=manifest,
        seed=17,
    )

    _, arrays = load_corpus(output)
    assert result["episodes"] == 1
    assert result["samples"] == 4
    assert result["wait_samples"] == 2
    assert result["deployment_samples"] == 2
    assert arrays["episode_starts"].tolist() == [True, False, False, False]
    assert arrays["expert_actions"].tolist() == [2, 0, 2, 1]
    assert arrays["previous_actions"].tolist() == [2, 2, 0, 2]
    with np.load(output, allow_pickle=False) as stored:
        assert stored["source_frames"].tolist() == [10, 20, 30, 40]


def test_provenance_split_is_global_by_replay_uuid(tmp_path: Path) -> None:
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    train = tmp_path / "train.npz"
    holdout = tmp_path / "holdout.npz"
    manifest = tmp_path / "split.json"
    _write_corpus(first, episode_ids=[0, 0, 1, 1], marker=1.0)
    _write_corpus(second, episode_ids=[4, 4, 5, 5], marker=2.0)
    for path, replays, arenas in (
        (first, ["shared", "shared", "first-only", "first-only"], ["a"] * 4),
        (second, ["shared", "shared", "second-only", "second-only"], ["b"] * 4),
    ):
        with np.load(path, allow_pickle=False) as stored:
            payload = {name: stored[name].copy() for name in stored.files}
        payload.update(
            {
                "source_replays": np.asarray(replays),
                "source_frames": np.asarray([1, 2, 1, 2], dtype=np.int64),
                "source_arenas": np.asarray(arenas),
            }
        )
        atomic_save_npz(path, payload)

    result = split_provenance_corpora(
        sources=[first, second],
        train_output_path=train,
        holdout_output_path=holdout,
        manifest_path=manifest,
        seed=23,
        holdout_fraction=1 / 3,
    )

    assert result["unique_replays"] == 3
    assert result["replay_overlap"] == 0
    assert result["train"]["samples"] + result["holdout"]["samples"] == 6
    assert result["train"]["episodes"] + result["holdout"]["episodes"] == 3
    with np.load(train, allow_pickle=False) as train_data, np.load(
        holdout, allow_pickle=False
    ) as holdout_data:
        train_replays = set(train_data["source_replays"].tolist())
        holdout_replays = set(holdout_data["source_replays"].tolist())
        assert train_replays.isdisjoint(holdout_replays)
        assert train_data["episode_starts"][0]
        assert holdout_data["episode_starts"][0]


def test_provenance_merge_can_prefer_first_source_on_conflict(
    tmp_path: Path,
) -> None:
    deployments = tmp_path / "deployments.npz"
    waits = tmp_path / "waits.npz"
    output = tmp_path / "chronological.npz"
    manifest = tmp_path / "chronological.json"
    _write_corpus(deployments, episode_ids=[0, 0], marker=1.0)
    _write_corpus(waits, episode_ids=[3, 3], marker=2.0)
    for path, frames in ((deployments, [10, 20]), (waits, [10, 30])):
        with np.load(path, allow_pickle=False) as stored:
            payload = {name: stored[name].copy() for name in stored.files}
        if path == waits:
            payload["expert_actions"] = np.full(2, 2, dtype=np.int64)
        payload.update(
            {
                "source_replays": np.asarray(["shared", "shared"]),
                "source_frames": np.asarray(frames, dtype=np.int64),
                "source_arenas": np.asarray(["arena_28", "arena_28"]),
            }
        )
        atomic_save_npz(path, payload)

    result = merge_provenance_corpora(
        sources=[deployments, waits],
        output_path=output,
        manifest_path=manifest,
        seed=19,
        conflict_policy="prefer-first",
    )

    _, arrays = load_corpus(output)
    assert result["conflicting_frames"] == 1
    assert result["conflicting_frames_removed"] == 0
    assert result["conflict_policy"] == "prefer-first"
    assert arrays["expert_actions"].tolist() == [0, 1, 2]
