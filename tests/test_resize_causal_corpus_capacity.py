from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.resize_causal_corpus_capacity import resize


def _save(path: Path, values: dict[str, np.ndarray]) -> None:
    with path.open("wb") as stream:
        np.savez_compressed(stream, **values)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_resize_drops_whole_episode_and_preserves_alignment(tmp_path: Path) -> None:
    samples = 6
    episode_ids = np.asarray([0, 0, 1, 1, 2, 2], dtype=np.int64)
    entity_mask = np.zeros((samples, 5), dtype=np.bool_)
    entity_mask[:, :2] = True
    entity_mask[2, :5] = True
    expert_actions = np.arange(samples, dtype=np.int64)
    source_frames = np.arange(samples, dtype=np.int64) + 10
    metadata = np.asarray(
        json.dumps(
            {
                "max_entities": 5,
                "samples": samples,
                "decisions": samples,
                "token_names": ["<pad>", "<unknown>"],
            }
        )
    )
    corpus = {
        "episode_ids": episode_ids,
        "expert_actions": expert_actions,
        "source_frames": source_frames,
        "entity_mask": entity_mask,
        "entity_ids": np.arange(samples * 5, dtype=np.int64).reshape(samples, 5),
        "entity_features": np.zeros((samples, 5, 32), dtype=np.float32),
        "metadata_json": metadata,
    }
    sidecar = {
        "episode_ids": episode_ids.copy(),
        "expert_actions": expert_actions.copy(),
        "source_frames": source_frames.copy(),
        "entity_mask": entity_mask.copy(),
        "entity_ids": corpus["entity_ids"].copy(),
        "entity_features": corpus["entity_features"].copy(),
        "entity_id_confidence": np.ones((samples, 5), dtype=np.float32),
        "entity_feature_confidence": np.ones((samples, 5, 32), dtype=np.float32),
    }
    corpus_path = tmp_path / "source.npz"
    sidecar_path = tmp_path / "source_sidecar.npz"
    corpus_out = tmp_path / "resized.npz"
    sidecar_out = tmp_path / "resized_sidecar.npz"
    manifest = tmp_path / "manifest.json"
    _save(corpus_path, corpus)
    _save(sidecar_path, sidecar)
    source_hashes = (_sha256(corpus_path), _sha256(sidecar_path))

    result = resize(
        corpus_path=corpus_path,
        sidecar_path=sidecar_path,
        capacity=4,
        corpus_out=corpus_out,
        sidecar_out=sidecar_out,
        manifest_out=manifest,
    )

    assert result["dropped"] == {
        "rows_over_capacity": 1,
        "episodes": 1,
        "samples": 2,
        "episode_ids": [1],
    }
    with np.load(corpus_out, allow_pickle=False) as resized:
        assert resized["entity_mask"].shape == (4, 4)
        assert resized["entity_features"].shape == (4, 4, 32)
        assert resized["episode_ids"].tolist() == [0, 0, 1, 1]
        assert resized["expert_actions"].tolist() == [0, 1, 4, 5]
        metadata_out = json.loads(str(resized["metadata_json"].item()))
        assert metadata_out["max_entities"] == 4
        assert metadata_out["samples"] == 4
    with np.load(sidecar_out, allow_pickle=False) as resized:
        assert resized["entity_id_confidence"].shape == (4, 4)
        assert resized["expert_actions"].tolist() == [0, 1, 4, 5]
    assert json.loads(manifest.read_text())["output"]["capacity"] == 4
    assert (_sha256(corpus_path), _sha256(sidecar_path)) == source_hashes


def test_resize_refuses_to_overwrite_source(tmp_path: Path) -> None:
    source = tmp_path / "source.npz"
    sidecar = tmp_path / "sidecar.npz"
    source.write_bytes(b"source")
    sidecar.write_bytes(b"sidecar")

    try:
        resize(
            corpus_path=source,
            sidecar_path=sidecar,
            capacity=4,
            corpus_out=source,
            sidecar_out=tmp_path / "out-sidecar.npz",
            manifest_out=tmp_path / "manifest.json",
        )
    except ValueError as error:
        assert str(error) == "capacity resize refuses to overwrite source artifacts"
    else:
        raise AssertionError("source overwrite should fail before loading inputs")
