from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np

from .imitation import CorpusMetadata, load_corpus
from .oracle_corpus import (
    CORPUS_ARRAY_NAMES,
    atomic_save_npz,
    atomic_write_json,
    file_sha256,
)

DEFAULT_ENTITY_FEATURE_DTYPE = np.dtype(np.float16)

_SAMPLE_IDENTITY_ARRAYS = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "hand_ids",
    "global_features",
    "action_masks",
    "expert_actions",
)


def _sample_fingerprint(arrays: dict[str, np.ndarray], row: int) -> bytes:
    """Return an exact identity for one supervised observation/action pair."""
    digest = hashlib.sha256()
    for name in _SAMPLE_IDENTITY_ARRAYS:
        value = np.ascontiguousarray(arrays[name][row])
        digest.update(name.encode("ascii"))
        digest.update(value.dtype.str.encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.digest()


def _deduplicated_episode_rows(
    arrays: dict[str, np.ndarray],
    selected: np.ndarray,
    *,
    seen_episodes: set[bytes],
) -> tuple[np.ndarray, int, int]:
    """Drop within-episode frames and exactly repeated whole episodes."""
    episode_ids = arrays["episode_ids"][selected]
    retained: list[int] = []
    duplicate_samples = 0
    duplicate_episodes = 0
    unique_episode_ids, first_indices = np.unique(episode_ids, return_index=True)
    episode_order = np.argsort(first_indices)
    for episode_id in unique_episode_ids[episode_order]:
        episode_rows = selected[episode_ids == episode_id]
        episode_retained: list[int] = []
        episode_samples: list[bytes] = []
        local_seen: set[bytes] = set()
        for row in episode_rows.tolist():
            fingerprint = _sample_fingerprint(arrays, row)
            if fingerprint in local_seen:
                duplicate_samples += 1
                continue
            local_seen.add(fingerprint)
            episode_retained.append(row)
            episode_samples.append(fingerprint)
        episode_digest = hashlib.sha256(b"".join(episode_samples)).digest()
        if episode_digest in seen_episodes:
            duplicate_samples += len(episode_retained)
            duplicate_episodes += 1
            continue
        seen_episodes.add(episode_digest)
        retained.extend(episode_retained)
    return (
        np.asarray(retained, dtype=np.int64),
        duplicate_samples,
        duplicate_episodes,
    )


def _selected_episode_rows(
    episode_ids: np.ndarray,
    *,
    target_samples: int | None,
    rng: np.random.Generator,
) -> tuple[np.ndarray, int]:
    """Select complete episodes near a sample target without breaking sequences."""
    unique, first, counts = np.unique(
        episode_ids, return_index=True, return_counts=True
    )
    order = np.argsort(first)
    unique = unique[order]
    first = first[order]
    counts = counts[order]
    for start, count in zip(first.tolist(), counts.tolist(), strict=True):
        rows = episode_ids[start : start + count]
        if rows.size != count or not np.all(rows == rows[0]):
            raise ValueError("source corpus episode samples must be contiguous")
    if target_samples is None or target_samples >= episode_ids.size:
        chosen = unique
    elif target_samples <= 0:
        raise ValueError("source target samples must be positive")
    else:
        shuffled = unique[rng.permutation(unique.size)]
        chosen_list: list[int] = []
        selected_count = 0
        count_by_episode = dict(zip(unique.tolist(), counts.tolist(), strict=True))
        for episode in shuffled.tolist():
            chosen_list.append(int(episode))
            selected_count += int(count_by_episode[episode])
            if selected_count >= target_samples:
                break
        chosen = np.asarray(chosen_list, dtype=episode_ids.dtype)
    selected = np.flatnonzero(np.isin(episode_ids, chosen)).astype(
        np.int64, copy=False
    )
    return selected, int(chosen.size)


def combine_imitation_corpora(
    *,
    sources: Sequence[Path],
    output_path: Path,
    manifest_path: Path,
    seed: int,
    target_samples: Sequence[int | None] | None = None,
    entity_feature_dtype: np.dtype[Any] = DEFAULT_ENTITY_FEATURE_DTYPE,
    deduplicate: bool = True,
    allow_mixed_decision_intervals: bool = False,
    independent_rows: bool = False,
    sample_masks: Sequence[np.ndarray | None] | None = None,
) -> dict[str, Any]:
    """Combine compatible corpora using deterministic whole-episode sampling."""
    if not sources:
        raise ValueError("at least one source corpus is required")
    if target_samples is None:
        target_samples = [None] * len(sources)
    if len(target_samples) != len(sources):
        raise ValueError("target sample counts must match source corpus count")
    if sample_masks is None:
        sample_masks = [None] * len(sources)
    if len(sample_masks) != len(sources):
        raise ValueError("sample masks must match source corpus count")
    if not independent_rows and any(mask is not None for mask in sample_masks):
        raise ValueError("sample masks require independent_rows=True")

    rng = np.random.default_rng(seed)
    combined: dict[str, list[np.ndarray]] = {
        name: [] for name in CORPUS_ARRAY_NAMES
    }
    source_records: list[dict[str, Any]] = []
    reference: CorpusMetadata | None = None
    next_episode_id = 0
    total_decisions = 0
    maximum_ticks = 0
    seen_episodes: set[bytes] = set()

    for source_index, (source, target, sample_mask) in enumerate(
        zip(sources, target_samples, sample_masks, strict=True)
    ):
        metadata, arrays = load_corpus(source)
        if reference is None:
            reference = metadata
        else:
            if metadata.max_entities != reference.max_entities:
                raise ValueError("source corpora use different max_entities")
            if metadata.token_names != reference.token_names:
                raise ValueError("source corpora use different token vocabularies")
            if (
                not allow_mixed_decision_intervals
                and metadata.decision_interval != reference.decision_interval
            ):
                raise ValueError("source corpora use different decision intervals")
            if metadata.reward_profile != reference.reward_profile:
                raise ValueError("source corpora use different reward profiles")

        selected, selected_episodes = _selected_episode_rows(
            arrays["episode_ids"],
            target_samples=target,
            rng=rng,
        )
        filtered_samples = 0
        if sample_mask is not None:
            mask = np.asarray(sample_mask, dtype=np.bool_)
            if mask.shape != (metadata.samples,):
                raise ValueError("source sample mask has an invalid shape")
            before_filter = int(selected.size)
            selected = selected[mask[selected]]
            filtered_samples = before_filter - int(selected.size)
        maximum_ticks = max(maximum_ticks, metadata.max_ticks)
        duplicate_samples = 0
        duplicate_episodes = 0
        if deduplicate:
            selected, duplicate_samples, duplicate_episodes = (
                _deduplicated_episode_rows(
                    arrays,
                    selected,
                    seen_episodes=seen_episodes,
                )
            )
        if selected.size == 0:
            source_records.append(
                {
                    "source_index": source_index,
                    "path": str(source.resolve()),
                    "sha256": file_sha256(source),
                    "source_samples": metadata.samples,
                    "selected_samples": 0,
                    "selected_episodes": 0,
                    "duplicate_samples_removed": duplicate_samples,
                    "duplicate_episodes_removed": duplicate_episodes,
                    "filtered_samples_removed": filtered_samples,
                    "decision_interval": metadata.decision_interval,
                    "label_source": metadata.label_source,
                    "behavior_checkpoint": metadata.behavior_checkpoint,
                    "behavior_opponent": metadata.behavior_opponent,
                }
            )
            continue

        selected_episode_ids = arrays["episode_ids"][selected]
        episode_boundaries = np.concatenate(
            (
                np.asarray([True]),
                selected_episode_ids[1:] != selected_episode_ids[:-1],
            )
        )
        renumbered = (
            np.cumsum(episode_boundaries, dtype=np.int64) - 1 + next_episode_id
        )
        selected_episodes = int(episode_boundaries.sum())
        next_episode_id += selected_episodes

        for name in CORPUS_ARRAY_NAMES:
            values = arrays[name][selected]
            if name == "episode_ids":
                values = renumbered
            elif name == "episode_starts":
                values = episode_boundaries
            elif name == "previous_actions":
                values = values.copy()
                noop_action = arrays["action_masks"].shape[-1] - 2
                values[episode_boundaries] = noop_action
                # Preserve the source behavior action for every non-start row.
                # Oracle/DAgger labels may differ from the action that actually
                # generated the next state, so deriving causal history from the
                # previous expert target fabricates an impossible trajectory.
            elif name == "entity_features":
                values = values.astype(entity_feature_dtype, copy=False)
            combined[name].append(values)
        total_decisions += int(selected.size)
        source_records.append(
            {
                "source_index": source_index,
                "path": str(source.resolve()),
                "sha256": file_sha256(source),
                "source_samples": metadata.samples,
                "selected_samples": int(selected.size),
                "selected_episodes": selected_episodes,
                "duplicate_samples_removed": duplicate_samples,
                "duplicate_episodes_removed": duplicate_episodes,
                "filtered_samples_removed": filtered_samples,
                "decision_interval": metadata.decision_interval,
                "label_source": metadata.label_source,
                "behavior_checkpoint": metadata.behavior_checkpoint,
                "behavior_opponent": metadata.behavior_opponent,
            }
        )

    assert reference is not None
    decision_intervals = {
        int(record["decision_interval"]) for record in source_records
    }
    output_arrays = {
        name: np.concatenate(parts, axis=0)
        for name, parts in combined.items()
    }
    samples = int(output_arrays["expert_actions"].shape[0])
    if independent_rows:
        # Sparse labels such as deployment clocks omit intervening decisions.
        # Treating adjacent recovered labels as a recurrent trajectory would
        # invent false previous-action and memory context.  Make that contract
        # structural: each retained observation is its own one-step episode.
        noop_action = output_arrays["action_masks"].shape[-1] - 2
        output_arrays["episode_ids"] = np.arange(samples, dtype=np.int64)
        output_arrays["episode_starts"] = np.ones(samples, dtype=np.bool_)
        output_arrays["previous_actions"] = np.full(
            samples, noop_action, dtype=np.int64
        )
        output_arrays["previous_rewards"] = np.zeros(samples, dtype=np.float32)
        next_episode_id = samples
    legal = output_arrays["action_masks"][
        np.arange(samples), output_arrays["expert_actions"]
    ]
    if not np.all(legal):
        raise ValueError("combined corpus contains an illegal expert action")
    mixed_metadata = CorpusMetadata(
        schema_version=reference.schema_version,
        created_at=np.datetime_as_string(np.datetime64("now"), timezone="UTC"),
        seed=seed,
        decisions=total_decisions,
        samples=samples,
        decision_interval=(
            reference.decision_interval if len(decision_intervals) == 1 else 0
        ),
        max_ticks=maximum_ticks,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=reference.max_entities,
        token_names=reference.token_names,
        reward_profile=reference.reward_profile,
        workers=1,
        behavior_checkpoint=None,
        expert_probability=1.0,
        stable_root_candidates=False,
        behavior_opponent=None,
        label_source="mixed-rehearsal",
    )
    payload = dict(output_arrays)
    payload["metadata_json"] = np.asarray(mixed_metadata.to_json())
    atomic_save_npz(output_path, payload)
    manifest = {
        "schema_version": 1,
        "output": str(output_path.resolve()),
        "output_sha256": file_sha256(output_path),
        "seed": seed,
        "samples": samples,
        "episodes": next_episode_id,
        "entity_feature_dtype": str(np.dtype(entity_feature_dtype)),
        "deduplicate": deduplicate,
        "allow_mixed_decision_intervals": allow_mixed_decision_intervals,
        "independent_rows": independent_rows,
        "previous_action_policy": "preserve-source-behavior",
        "sources": source_records,
        "metadata": asdict(mixed_metadata),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def _load_provenance_corpus(
    path: Path,
) -> tuple[CorpusMetadata, dict[str, np.ndarray], dict[str, np.ndarray]]:
    metadata, arrays = load_corpus(path)
    with np.load(path, allow_pickle=False) as payload:
        required = {"source_replays", "source_frames", "source_arenas"}
        missing = required.difference(payload.files)
        if missing:
            raise ValueError(
                f"provenance corpus {path} is missing arrays: {sorted(missing)}"
            )
        provenance = {name: payload[name].copy() for name in required}
    for name, values in provenance.items():
        if values.shape != (metadata.samples,):
            raise ValueError(f"provenance array {name} has an invalid shape")
    return metadata, arrays, provenance


def merge_provenance_corpora(
    *,
    sources: Sequence[Path],
    output_path: Path,
    manifest_path: Path,
    seed: int,
    require_mixed_actions: bool = True,
    conflict_policy: str = "drop",
    entity_feature_dtype: np.dtype[Any] = DEFAULT_ENTITY_FEATURE_DTYPE,
) -> dict[str, Any]:
    """Merge labeled moments by their original replay and frame chronology."""
    if len(sources) < 2:
        raise ValueError("chronological merge requires at least two sources")
    if conflict_policy not in {"drop", "prefer-first"}:
        raise ValueError("conflict_policy must be 'drop' or 'prefer-first'")
    loaded = [_load_provenance_corpus(source) for source in sources]
    reference = loaded[0][0]
    for metadata, _, _ in loaded[1:]:
        if metadata.max_entities != reference.max_entities:
            raise ValueError("source corpora use different max_entities")
        if metadata.token_names != reference.token_names:
            raise ValueError("source corpora use different token vocabularies")
        if metadata.decision_interval != reference.decision_interval:
            raise ValueError("source corpora use different decision intervals")
        if metadata.reward_profile != reference.reward_profile:
            raise ValueError("source corpora use different reward profiles")

    replay_sets = [set(provenance["source_replays"].tolist()) for _, _, provenance in loaded]
    shared_replays = set.intersection(*replay_sets)
    output_parts: dict[str, list[np.ndarray]] = {
        name: [] for name in CORPUS_ARRAY_NAMES
    }
    output_replays: list[str] = []
    output_frames: list[int] = []
    output_arenas: list[str] = []
    output_sources: list[int] = []
    conflicting_frames = 0
    repeated_frames = 0
    skipped_single_label_episodes = 0
    episode_id = 0
    noop_action = loaded[0][1]["action_masks"].shape[-1] - 2

    for replay in sorted(shared_replays):
        moments: list[tuple[int, int, int]] = []
        for source_index, (_, _, provenance) in enumerate(loaded):
            rows = np.flatnonzero(provenance["source_replays"] == replay)
            moments.extend(
                (int(provenance["source_frames"][row]), source_index, int(row))
                for row in rows.tolist()
            )
        moments.sort()
        chosen: list[tuple[int, int, int]] = []
        for frame, source_index, row in moments:
            if chosen and chosen[-1][0] == frame:
                previous_source = chosen[-1][1]
                previous_row = chosen[-1][2]
                previous_action = int(
                    loaded[previous_source][1]["expert_actions"][previous_row]
                )
                action = int(loaded[source_index][1]["expert_actions"][row])
                if action != previous_action:
                    conflicting_frames += 1
                    if conflict_policy == "drop":
                        chosen.pop()
                else:
                    repeated_frames += 1
                continue
            chosen.append((frame, source_index, row))
        if not chosen:
            continue
        actions = np.asarray(
            [loaded[source][1]["expert_actions"][row] for _, source, row in chosen],
            dtype=np.int64,
        )
        has_wait = bool(np.any(actions == noop_action))
        has_deployment = bool(np.any(actions < noop_action))
        if require_mixed_actions and not (has_wait and has_deployment):
            skipped_single_label_episodes += 1
            continue

        for local_index, (frame, source_index, row) in enumerate(chosen):
            _, arrays, provenance = loaded[source_index]
            for name in CORPUS_ARRAY_NAMES:
                if name == "episode_ids":
                    value = np.asarray(episode_id, dtype=np.int64)
                elif name == "episode_starts":
                    value = np.asarray(local_index == 0, dtype=np.bool_)
                elif name == "previous_actions":
                    previous = noop_action if local_index == 0 else int(actions[local_index - 1])
                    value = np.asarray(previous, dtype=np.int64)
                elif name == "previous_rewards":
                    value = np.asarray(0.0, dtype=np.float32)
                else:
                    value = arrays[name][row]
                output_parts[name].append(np.asarray(value))
            output_replays.append(replay)
            output_frames.append(frame)
            output_arenas.append(str(provenance["source_arenas"][row]))
            output_sources.append(source_index)
        episode_id += 1

    if episode_id == 0:
        raise ValueError("no mixed chronological replay episodes survived")
    output_arrays = {
        name: np.stack(parts)
        for name, parts in output_parts.items()
    }
    output_arrays["entity_features"] = output_arrays["entity_features"].astype(
        entity_feature_dtype,
        copy=False,
    )
    samples = int(output_arrays["expert_actions"].shape[0])
    legal = output_arrays["action_masks"][
        np.arange(samples), output_arrays["expert_actions"]
    ]
    if not np.all(legal):
        raise ValueError("chronological corpus contains an illegal expert action")
    mixed_metadata = CorpusMetadata(
        schema_version=reference.schema_version,
        created_at=np.datetime_as_string(np.datetime64("now"), timezone="UTC"),
        seed=seed,
        decisions=samples,
        samples=samples,
        decision_interval=reference.decision_interval,
        max_ticks=max(metadata.max_ticks for metadata, _, _ in loaded),
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=reference.max_entities,
        token_names=reference.token_names,
        reward_profile=reference.reward_profile,
        workers=1,
        behavior_checkpoint=None,
        expert_probability=1.0,
        stable_root_candidates=False,
        behavior_opponent=None,
        label_source="tv-royale-human-chronological",
    )
    payload = dict(output_arrays)
    payload.update(
        {
            "source_replays": np.asarray(output_replays, dtype=np.str_),
            "source_frames": np.asarray(output_frames, dtype=np.int64),
            "source_arenas": np.asarray(output_arenas, dtype=np.str_),
            "source_corpus_indices": np.asarray(output_sources, dtype=np.int64),
            "metadata_json": np.asarray(mixed_metadata.to_json()),
        }
    )
    atomic_save_npz(output_path, payload)
    manifest = {
        "schema_version": 1,
        "output": str(output_path.resolve()),
        "output_sha256": file_sha256(output_path),
        "seed": seed,
        "samples": samples,
        "episodes": episode_id,
        "wait_samples": int(np.sum(output_arrays["expert_actions"] == noop_action)),
        "deployment_samples": int(np.sum(output_arrays["expert_actions"] < noop_action)),
        "shared_source_replays": len(shared_replays),
        "skipped_single_label_episodes": skipped_single_label_episodes,
        "conflicting_frames": conflicting_frames,
        "conflicting_frames_removed": (
            conflicting_frames if conflict_policy == "drop" else 0
        ),
        "repeated_frames_removed": repeated_frames,
        "require_mixed_actions": require_mixed_actions,
        "conflict_policy": conflict_policy,
        "entity_feature_dtype": str(np.dtype(entity_feature_dtype)),
        "sources": [
            {
                "path": str(source.resolve()),
                "sha256": file_sha256(source),
                "samples": metadata.samples,
                "label_source": metadata.label_source,
            }
            for source, (metadata, _, _) in zip(sources, loaded, strict=True)
        ],
        "metadata": asdict(mixed_metadata),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def split_provenance_corpora(
    *,
    sources: Sequence[Path],
    train_output_path: Path,
    holdout_output_path: Path,
    manifest_path: Path,
    seed: int,
    holdout_fraction: float,
    entity_feature_dtype: np.dtype[Any] = DEFAULT_ENTITY_FEATURE_DTYPE,
) -> dict[str, Any]:
    """Split complete public replays globally, preserving chronological episodes.

    Replay UUIDs, rather than source filenames or arena labels, are the leakage
    boundary.  A replay appearing in multiple provenance corpora is therefore
    assigned to exactly one side of the split.
    """
    if not sources:
        raise ValueError("at least one provenance corpus is required")
    if not 0.0 < holdout_fraction < 1.0:
        raise ValueError("holdout_fraction must be in (0, 1)")

    loaded = [_load_provenance_corpus(source) for source in sources]
    reference = loaded[0][0]
    for metadata, _, _ in loaded[1:]:
        if metadata.max_entities != reference.max_entities:
            raise ValueError("source corpora use different max_entities")
        if metadata.token_names != reference.token_names:
            raise ValueError("source corpora use different token vocabularies")
        if metadata.decision_interval != reference.decision_interval:
            raise ValueError("source corpora use different decision intervals")
        if metadata.reward_profile != reference.reward_profile:
            raise ValueError("source corpora use different reward profiles")

    replay_ids = sorted(
        {
            str(replay)
            for _, _, provenance in loaded
            for replay in provenance["source_replays"].tolist()
        }
    )
    if len(replay_ids) < 2:
        raise ValueError("provenance split requires at least two unique replays")
    ranked = sorted(
        replay_ids,
        key=lambda replay: hashlib.sha256(
            f"{seed}:{replay}".encode()
        ).digest(),
    )
    holdout_count = min(
        len(ranked) - 1,
        max(1, round(len(ranked) * holdout_fraction)),
    )
    holdout_replays = frozenset(ranked[:holdout_count])
    train_replays = frozenset(ranked[holdout_count:])
    preferred_source_by_replay: dict[str, int] = {}
    preferred_rows_by_replay: dict[str, int] = {}
    for source_index, (_, arrays, provenance) in enumerate(loaded):
        replays, counts = np.unique(
            provenance["source_replays"], return_counts=True
        )
        for replay_value, count_value in zip(
            replays.tolist(), counts.tolist(), strict=True
        ):
            replay = str(replay_value)
            rows = np.flatnonzero(provenance["source_replays"] == replay_value)
            if np.unique(arrays["episode_ids"][rows]).size != 1:
                raise ValueError(
                    f"source corpus contains multiple episodes for replay {replay}"
                )
            count = int(count_value)
            if count > preferred_rows_by_replay.get(replay, -1):
                preferred_source_by_replay[replay] = source_index
                preferred_rows_by_replay[replay] = count

    def publish_split(
        *,
        name: str,
        selected_replays: frozenset[str],
        output_path: Path,
    ) -> dict[str, Any]:
        combined: dict[str, list[np.ndarray]] = {
            key: [] for key in CORPUS_ARRAY_NAMES
        }
        provenance_parts: dict[str, list[np.ndarray]] = {
            key: [] for key in ("source_replays", "source_frames", "source_arenas")
        }
        source_records: list[dict[str, Any]] = []
        next_episode_id = 0
        for source_index, (source, (metadata, arrays, provenance)) in enumerate(
            zip(sources, loaded, strict=True)
        ):
            replay_values = provenance["source_replays"].astype(str)
            assigned_here = np.fromiter(
                (
                    preferred_source_by_replay[replay] == source_index
                    for replay in replay_values.tolist()
                ),
                dtype=np.bool_,
                count=replay_values.size,
            )
            selected = np.flatnonzero(
                np.isin(
                    replay_values,
                    np.asarray(sorted(selected_replays), dtype=np.str_),
                )
                & assigned_here
            )
            duplicate_variant_rows = int(
                np.sum(np.isin(replay_values, list(selected_replays)))
                - selected.size
            )
            if selected.size == 0:
                source_records.append(
                    {
                        "path": str(source.resolve()),
                        "sha256": file_sha256(source),
                        "samples": 0,
                        "episodes": 0,
                        "replays": 0,
                        "arenas": {},
                        "duplicate_replay_variant_rows_removed": (
                            duplicate_variant_rows
                        ),
                    }
                )
                continue
            selected_episode_ids = arrays["episode_ids"][selected]
            boundaries = np.concatenate(
                (
                    np.asarray([True]),
                    selected_episode_ids[1:] != selected_episode_ids[:-1],
                )
            )
            renumbered = (
                np.cumsum(boundaries, dtype=np.int64) - 1 + next_episode_id
            )
            episodes = int(boundaries.sum())
            next_episode_id += episodes
            for key in CORPUS_ARRAY_NAMES:
                values = arrays[key][selected]
                if key == "episode_ids":
                    values = renumbered
                elif key == "episode_starts":
                    values = boundaries
                elif key == "entity_features":
                    values = values.astype(entity_feature_dtype, copy=False)
                combined[key].append(values)
            for key, parts in provenance_parts.items():
                parts.append(provenance[key][selected])
            arenas, arena_counts = np.unique(
                provenance["source_arenas"][selected], return_counts=True
            )
            source_records.append(
                {
                    "path": str(source.resolve()),
                    "sha256": file_sha256(source),
                    "samples": int(selected.size),
                    "episodes": episodes,
                    "replays": int(
                        np.unique(provenance["source_replays"][selected]).size
                    ),
                    "arenas": {
                        str(arena): int(count)
                        for arena, count in zip(
                            arenas.tolist(), arena_counts.tolist(), strict=True
                        )
                    },
                    "duplicate_replay_variant_rows_removed": (
                        duplicate_variant_rows
                    ),
                    "label_source": metadata.label_source,
                }
            )
        if not combined["expert_actions"]:
            raise ValueError(f"{name} split has no samples")
        output_arrays = {
            key: np.concatenate(parts, axis=0) for key, parts in combined.items()
        }
        output_provenance = {
            key: np.concatenate(parts, axis=0)
            for key, parts in provenance_parts.items()
        }
        samples = int(output_arrays["expert_actions"].shape[0])
        legal = output_arrays["action_masks"][
            np.arange(samples), output_arrays["expert_actions"]
        ]
        if not np.all(legal):
            raise ValueError(f"{name} split contains an illegal expert action")
        split_metadata = replace(
            reference,
            created_at=np.datetime_as_string(np.datetime64("now"), timezone="UTC"),
            seed=seed,
            decisions=samples,
            samples=samples,
            max_ticks=max(metadata.max_ticks for metadata, _, _ in loaded),
            workers=1,
            behavior_checkpoint=None,
            behavior_opponent=None,
            label_source=f"tv-royale-human-{name}",
        )
        payload = dict(output_arrays)
        payload.update(output_provenance)
        payload["metadata_json"] = np.asarray(split_metadata.to_json())
        atomic_save_npz(output_path, payload)
        return {
            "output": str(output_path.resolve()),
            "output_sha256": file_sha256(output_path),
            "samples": samples,
            "episodes": next_episode_id,
            "replays": len(selected_replays),
            "sources": source_records,
            "metadata": asdict(split_metadata),
        }

    train_record = publish_split(
        name="train",
        selected_replays=train_replays,
        output_path=train_output_path,
    )
    holdout_record = publish_split(
        name="holdout",
        selected_replays=holdout_replays,
        output_path=holdout_output_path,
    )
    manifest = {
        "schema_version": 1,
        "seed": seed,
        "holdout_fraction": holdout_fraction,
        "unique_replays": len(replay_ids),
        "train_replay_ids": sorted(train_replays),
        "holdout_replay_ids": sorted(holdout_replays),
        "replay_overlap": len(train_replays.intersection(holdout_replays)),
        "train": train_record,
        "holdout": holdout_record,
    }
    atomic_write_json(manifest_path, manifest)
    return manifest
