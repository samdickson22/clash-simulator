from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO

import numpy as np

CORPUS_ARRAY_NAMES = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "hand_ids",
    "global_features",
    "action_masks",
    "previous_actions",
    "previous_rewards",
    "episode_starts",
    "expert_actions",
    "episode_ids",
)
SHARD_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CorpusShardSpec:
    corpus_fingerprint: str
    shard_index: int
    shard_count: int
    decisions: int
    seed: int
    schema_version: int = SHARD_SCHEMA_VERSION

    @property
    def samples(self) -> int:
        return 2 * self.decisions

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str) -> CorpusShardSpec:
        return cls(**json.loads(payload))


def corpus_fingerprint(config: Mapping[str, Any]) -> str:
    """Return a stable fingerprint for every output-affecting collection input."""
    canonical = json.dumps(
        config,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def shard_directory(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.name}.shards")


def shard_path(output_path: Path, shard_index: int, shard_count: int) -> Path:
    return shard_directory(output_path) / (
        f"part-{shard_index:05d}-of-{shard_count:05d}.npz"
    )


def manifest_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.name}.manifest.json")


def _atomic_publish(
    destination: Path,
    writer: Callable[[BinaryIO], None],
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as target:
            writer(target)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_save_npz(destination: Path, payload: Mapping[str, np.ndarray]) -> None:
    def write_npz(target: BinaryIO) -> None:
        np.savez_compressed(target, **dict(payload))  # type: ignore[arg-type]

    _atomic_publish(destination, write_npz)


def atomic_write_json(destination: Path, payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, indent=2, sort_keys=True).encode()

    def write_json(target: BinaryIO) -> None:
        target.write(serialized)

    _atomic_publish(destination, write_json)


def _validate_shard_arrays(
    arrays: Mapping[str, np.ndarray],
    spec: CorpusShardSpec,
) -> None:
    missing = set(CORPUS_ARRAY_NAMES).difference(arrays)
    if missing:
        raise ValueError(f"corpus shard is missing arrays: {sorted(missing)}")
    for name in CORPUS_ARRAY_NAMES:
        if arrays[name].shape[0] != spec.samples:
            raise ValueError(
                f"corpus shard {name} has {arrays[name].shape[0]} samples; "
                f"expected {spec.samples}"
            )
    expert_actions = arrays["expert_actions"]
    action_masks = arrays["action_masks"]
    if expert_actions.ndim != 1 or action_masks.ndim != 2:
        raise ValueError("corpus shard action arrays have invalid rank")
    if np.any(expert_actions < 0) or np.any(
        expert_actions >= action_masks.shape[1]
    ):
        raise ValueError("corpus shard expert action is out of range")
    legal = action_masks[np.arange(spec.samples), expert_actions]
    if not np.all(legal):
        raise ValueError("corpus shard contains an illegal expert action")


def publish_shard(
    destination: Path,
    spec: CorpusShardSpec,
    arrays: Mapping[str, np.ndarray],
) -> None:
    _validate_shard_arrays(arrays, spec)
    payload = {name: np.asarray(arrays[name]) for name in CORPUS_ARRAY_NAMES}
    payload["shard_json"] = np.asarray(spec.to_json())
    atomic_save_npz(destination, payload)


def load_shard(
    source: Path,
    expected: CorpusShardSpec,
) -> dict[str, np.ndarray]:
    with np.load(source, allow_pickle=False) as payload:
        actual = CorpusShardSpec.from_json(str(payload["shard_json"].item()))
        if actual != expected:
            raise ValueError(
                f"corpus shard metadata mismatch: expected {expected}, got {actual}"
            )
        arrays = {name: payload[name].copy() for name in CORPUS_ARRAY_NAMES}
    _validate_shard_arrays(arrays, expected)
    return arrays


def reusable_shard(
    source: Path,
    expected: CorpusShardSpec,
) -> bool:
    if not source.is_file():
        return False
    try:
        load_shard(source, expected)
    except (KeyError, OSError, ValueError):
        return False
    return True


def publish_manifest(
    output_path: Path,
    *,
    corpus_fingerprint: str,
    shard_count: int,
    completed_shards: list[int],
    complete: bool,
) -> None:
    atomic_write_json(
        manifest_path(output_path),
        {
            "schema_version": SHARD_SCHEMA_VERSION,
            "output": str(output_path),
            "corpus_fingerprint": corpus_fingerprint,
            "shard_count": shard_count,
            "completed_shards": sorted(completed_shards),
            "complete": complete,
        },
    )
