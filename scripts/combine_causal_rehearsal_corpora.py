#!/usr/bin/env python3
# mypy: disable-error-code="import-untyped"
"""Combine aligned causal rehearsal corpus/sidecar pairs without row leakage."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _save(path: Path, values: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, **values)  # type: ignore[arg-type]
    temporary.replace(path)


def combine(
    *,
    corpora: list[Path],
    sidecars: list[Path],
    corpus_out: Path,
    sidecar_out: Path,
    manifest_out: Path,
) -> dict[str, Any]:
    if len(corpora) != len(sidecars) or len(corpora) < 2:
        raise ValueError("at least two aligned corpus/sidecar pairs are required")
    corpus_payloads: list[dict[str, np.ndarray]] = []
    sidecar_payloads: list[dict[str, np.ndarray]] = []
    metadata_rows: list[dict[str, Any]] = []
    token_names: tuple[str, ...] | None = None
    max_entities: int | None = None
    episode_offset = 0
    for corpus_path, sidecar_path in zip(corpora, sidecars, strict=True):
        with np.load(corpus_path, allow_pickle=False) as payload:
            corpus = {name: payload[name].copy() for name in payload.files}
        with np.load(sidecar_path, allow_pickle=False) as payload:
            sidecar = {name: payload[name].copy() for name in payload.files}
        metadata = json.loads(str(corpus["metadata_json"].item()))
        names = tuple(str(value) for value in metadata["token_names"])
        entities = int(metadata["max_entities"])
        if token_names is None:
            token_names = names
            max_entities = entities
        elif names != token_names or entities != max_entities:
            raise ValueError("causal corpus vocabulary or entity capacity differs")
        samples = int(corpus["expert_actions"].size)
        for values, kind in ((corpus, "corpus"), (sidecar, "sidecar")):
            for name, value in values.items():
                if value.ndim > 0 and value.shape[0] not in {samples}:
                    raise ValueError(f"{kind} array {name} is not sample-aligned")
        for name in ("expert_actions", "episode_ids", "source_frames"):
            if not np.array_equal(corpus[name], sidecar[name]):
                raise ValueError(f"sidecar {name} is not aligned")
        episode_ids = corpus["episode_ids"].astype(np.int64, copy=True)
        unique = np.unique(episode_ids)
        remap = {int(value): episode_offset + index for index, value in enumerate(unique)}
        remapped = np.asarray([remap[int(value)] for value in episode_ids], dtype=np.int64)
        corpus["episode_ids"] = remapped
        sidecar["episode_ids"] = remapped.copy()
        episode_offset += len(unique)
        corpus_payloads.append(corpus)
        sidecar_payloads.append(sidecar)
        metadata_rows.append(
            {
                "corpus": str(corpus_path.resolve()),
                "corpus_sha256": _sha(corpus_path),
                "sidecar": str(sidecar_path.resolve()),
                "sidecar_sha256": _sha(sidecar_path),
                "samples": samples,
                "episodes": len(unique),
                "label_source": metadata.get("label_source"),
            }
        )
    assert token_names is not None and max_entities is not None
    corpus_names = set(corpus_payloads[0]).difference({"metadata_json"})
    if any(set(payload).difference({"metadata_json"}) != corpus_names for payload in corpus_payloads):
        raise ValueError("causal corpus array schemas differ")
    sidecar_names = set(sidecar_payloads[0])
    if any(set(payload) != sidecar_names for payload in sidecar_payloads):
        raise ValueError("causal sidecar array schemas differ")
    combined_corpus = {
        name: np.concatenate([payload[name] for payload in corpus_payloads], axis=0)
        for name in sorted(corpus_names)
    }
    combined_metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "samples": int(combined_corpus["expert_actions"].size),
        "decisions": int(combined_corpus["expert_actions"].size),
        "seed": 0,
        "decision_interval": 8,
        "max_ticks": 6000,
        "planner_depth": 0,
        "planner_simulations": 0,
        "planner_action_samples": 0,
        "max_entities": max_entities,
        "token_names": list(token_names),
        "reward_profile": "objective-v1",
        "workers": 1,
        "behavior_checkpoint": None,
        "expert_probability": 1.0,
        "stable_root_candidates": False,
        "behavior_opponent": None,
        "label_source": "behavior",
        "label_strategy": None,
        "sampling_decks_path": None,
    }
    combined_corpus["metadata_json"] = np.asarray(
        json.dumps(combined_metadata, sort_keys=True)
    )
    scalar_sidecar_names = {
        "schema_version",
        "feature_contract_version",
        "action_mask_contract_version",
    }
    combined_sidecar: dict[str, np.ndarray] = {}
    for name in sorted(sidecar_names):
        if name in scalar_sidecar_names:
            first = sidecar_payloads[0][name]
            if any(not np.array_equal(payload[name], first) for payload in sidecar_payloads[1:]):
                raise ValueError(f"sidecar scalar {name} differs")
            combined_sidecar[name] = first
        else:
            combined_sidecar[name] = np.concatenate(
                [payload[name] for payload in sidecar_payloads], axis=0
            )
    _save(corpus_out, combined_corpus)
    _save(sidecar_out, combined_sidecar)
    result = {
        "schema": "clasher.combined_causal_rehearsal.v1",
        "corpus": str(corpus_out.resolve()),
        "corpus_sha256": _sha(corpus_out),
        "sidecar": str(sidecar_out.resolve()),
        "sidecar_sha256": _sha(sidecar_out),
        "samples": int(combined_corpus["expert_actions"].size),
        "episodes": episode_offset,
        "sources": metadata_rows,
    }
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", action="append", required=True, type=Path)
    parser.add_argument("--sidecar", action="append", required=True, type=Path)
    parser.add_argument("--corpus-out", required=True, type=Path)
    parser.add_argument("--sidecar-out", required=True, type=Path)
    parser.add_argument("--manifest-out", required=True, type=Path)
    args = parser.parse_args()
    result = combine(
        corpora=[path.resolve() for path in args.corpus],
        sidecars=[path.resolve() for path in args.sidecar],
        corpus_out=args.corpus_out.resolve(),
        sidecar_out=args.sidecar_out.resolve(),
        manifest_out=args.manifest_out.resolve(),
    )
    print(json.dumps({key: result[key] for key in ("samples", "episodes")}, sort_keys=True))


if __name__ == "__main__":
    main()
