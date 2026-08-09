import json
from pathlib import Path

import numpy as np

from clasher.rl.oracle_corpus import (
    CORPUS_ARRAY_NAMES,
    CorpusShardSpec,
    load_shard,
    manifest_path,
    publish_manifest,
    publish_shard,
    reusable_shard,
    shard_path,
)


def _shard_arrays() -> dict[str, np.ndarray]:
    arrays = {
        name: np.zeros((2, 1), dtype=np.float32) for name in CORPUS_ARRAY_NAMES
    }
    arrays["action_masks"] = np.asarray(
        [[True, True, False], [True, False, True]], dtype=np.bool_
    )
    arrays["expert_actions"] = np.asarray([1, 2], dtype=np.int64)
    arrays["episode_ids"] = np.asarray([0, 0], dtype=np.int64)
    return arrays


def test_atomic_shard_round_trip_and_manifest(tmp_path: Path):
    output = tmp_path / "oracle.npz"
    spec = CorpusShardSpec(
        corpus_fingerprint="abc123",
        shard_index=0,
        shard_count=1,
        decisions=1,
        seed=31,
    )
    part = shard_path(output, 0, 1)
    arrays = _shard_arrays()

    publish_shard(part, spec, arrays)
    publish_manifest(
        output,
        corpus_fingerprint=spec.corpus_fingerprint,
        shard_count=1,
        completed_shards=[0],
        complete=True,
    )

    assert reusable_shard(part, spec)
    assert not reusable_shard(
        part,
        CorpusShardSpec(
            corpus_fingerprint="different",
            shard_index=0,
            shard_count=1,
            decisions=1,
            seed=31,
        ),
    )
    loaded = load_shard(part, spec)
    for name in CORPUS_ARRAY_NAMES:
        np.testing.assert_array_equal(loaded[name], arrays[name])
    manifest = json.loads(manifest_path(output).read_text())
    assert manifest["completed_shards"] == [0]
    assert manifest["complete"] is True
    assert not list(tmp_path.rglob("*.tmp"))
