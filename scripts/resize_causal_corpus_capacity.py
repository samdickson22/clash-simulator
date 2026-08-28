#!/usr/bin/env python3
"""Resize an aligned causal corpus by dropping whole over-capacity episodes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

ENTITY_ARRAYS = {
    "entity_ids",
    "entity_features",
    "entity_mask",
    "entity_id_confidence",
    "entity_feature_confidence",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as payload:
        return {name: payload[name].copy() for name in payload.files}


def _save(path: Path, values: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, **values)  # type: ignore[arg-type]
    temporary.replace(path)


def _remap_episodes(values: np.ndarray) -> tuple[np.ndarray, int]:
    unique = np.unique(values)
    remap = {int(value): index for index, value in enumerate(unique.tolist())}
    return (
        np.asarray([remap[int(value)] for value in values], dtype=np.int64),
        len(unique),
    )


def resize(
    *,
    corpus_path: Path,
    sidecar_path: Path,
    capacity: int,
    corpus_out: Path,
    sidecar_out: Path,
    manifest_out: Path,
) -> dict[str, Any]:
    if capacity < 1:
        raise ValueError("capacity must be positive")
    input_paths = {corpus_path.resolve(), sidecar_path.resolve()}
    output_paths = {
        corpus_out.resolve(),
        sidecar_out.resolve(),
        manifest_out.resolve(),
    }
    if len(output_paths) != 3:
        raise ValueError("capacity resize outputs must be distinct")
    if input_paths & output_paths:
        raise ValueError("capacity resize refuses to overwrite source artifacts")
    corpus = _load(corpus_path)
    sidecar = _load(sidecar_path)
    samples = int(corpus["episode_ids"].size)
    if samples < 1:
        raise ValueError("source corpus is empty")
    for name in ("episode_ids", "expert_actions", "source_frames", "entity_mask"):
        if name not in corpus or name not in sidecar:
            raise ValueError(f"aligned input is missing {name}")
        if not np.array_equal(corpus[name], sidecar[name]):
            raise ValueError(f"aligned input differs for {name}")
    source_capacity = int(corpus["entity_mask"].shape[1])
    if capacity > source_capacity:
        raise ValueError("target capacity exceeds source capacity")
    entity_counts = corpus["entity_mask"].sum(axis=1, dtype=np.int64)
    offending_rows = entity_counts > capacity
    offending_episodes = np.unique(corpus["episode_ids"][offending_rows])
    keep = ~np.isin(corpus["episode_ids"], offending_episodes)
    if not bool(keep.any()):
        raise ValueError("capacity filter removes every episode")

    def filtered(payload: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        result: dict[str, np.ndarray] = {}
        for name, value in payload.items():
            if value.ndim > 0 and value.shape[0] == samples:
                selected = value[keep]
                if name in ENTITY_ARRAYS:
                    selected = selected[:, :capacity, ...]
                result[name] = selected
            else:
                result[name] = value
        return result

    resized_corpus = filtered(corpus)
    resized_sidecar = filtered(sidecar)
    remapped, retained_episodes = _remap_episodes(resized_corpus["episode_ids"])
    resized_corpus["episode_ids"] = remapped
    resized_sidecar["episode_ids"] = remapped.copy()
    metadata = json.loads(str(resized_corpus["metadata_json"].item()))
    metadata["max_entities"] = capacity
    metadata["samples"] = int(keep.sum())
    metadata["decisions"] = int(keep.sum())
    resized_corpus["metadata_json"] = np.asarray(
        json.dumps(metadata, sort_keys=True)
    )
    if not np.array_equal(
        resized_corpus["expert_actions"], resized_sidecar["expert_actions"]
    ):
        raise RuntimeError("capacity resize broke expert-action alignment")
    if int(resized_corpus["entity_mask"].sum(axis=1).max()) > capacity:
        raise RuntimeError("resized corpus still exceeds target capacity")

    _save(corpus_out, resized_corpus)
    _save(sidecar_out, resized_sidecar)
    result = {
        "schema_version": 1,
        "contract": "whole-episode-causal-capacity-resize-v1",
        "source": {
            "corpus": str(corpus_path.resolve()),
            "corpus_sha256": _sha256(corpus_path),
            "sidecar": str(sidecar_path.resolve()),
            "sidecar_sha256": _sha256(sidecar_path),
            "capacity": source_capacity,
            "samples": samples,
            "episodes": int(np.unique(corpus["episode_ids"]).size),
            "maximum_entities": int(entity_counts.max()),
        },
        "output": {
            "corpus": str(corpus_out.resolve()),
            "corpus_sha256": _sha256(corpus_out),
            "sidecar": str(sidecar_out.resolve()),
            "sidecar_sha256": _sha256(sidecar_out),
            "capacity": capacity,
            "samples": int(keep.sum()),
            "episodes": retained_episodes,
            "maximum_entities": int(resized_corpus["entity_mask"].sum(axis=1).max()),
        },
        "dropped": {
            "rows_over_capacity": int(offending_rows.sum()),
            "episodes": int(offending_episodes.size),
            "samples": int((~keep).sum()),
            "episode_ids": [int(value) for value in offending_episodes.tolist()],
        },
    }
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_temporary = manifest_out.with_name(f".{manifest_out.name}.tmp")
    manifest_temporary.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_temporary.replace(manifest_out)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--capacity", type=int, required=True)
    parser.add_argument("--corpus-out", type=Path, required=True)
    parser.add_argument("--sidecar-out", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = resize(
        corpus_path=args.corpus.resolve(),
        sidecar_path=args.sidecar.resolve(),
        capacity=args.capacity,
        corpus_out=args.corpus_out.resolve(),
        sidecar_out=args.sidecar_out.resolve(),
        manifest_out=args.manifest_out.resolve(),
    )
    print(json.dumps(result["dropped"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
