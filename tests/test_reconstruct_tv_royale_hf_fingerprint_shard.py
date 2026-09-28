from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image

from scripts.deduplicate_tv_royale_sources import load_hf_fingerprint_shards
from scripts.reconstruct_tv_royale_hf_fingerprint_shard import (
    build_reconstruction_plan,
    reconstruct_shard,
)


def _png(seed: int) -> bytes:
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 256, size=(960, 540, 3), dtype=np.uint8)
    output = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(output, format="PNG")
    return output.getvalue()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    source_root = tmp_path / "source"
    repo_path = Path("arena_12/replay-a/frames.parquet")
    source = source_root / repo_path
    source.parent.mkdir(parents=True)
    images = [_png(seed) for seed in range(10)]
    image_type = pa.struct([("bytes", pa.binary()), ("path", pa.string())])
    table = pa.table(
        {
            "frame_id": pa.array([0, 7, 20, 30, 41, 52, 60, 71, 83, 100]),
            "image": pa.array(
                [
                    {"bytes": image, "path": f"frame-{index}.png"}
                    for index, image in enumerate(images)
                ],
                type=image_type,
            ),
            "hash": pa.array([hashlib.md5(image).hexdigest() for image in images]),
        }
    )
    pq.write_table(table, source, compression="zstd")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()

    game = tmp_path / "derived" / "games" / "arena_12" / "replay-a"
    game.mkdir(parents=True)
    audit = game / "audit-event.png"
    audit.write_bytes(images[4])
    (game / "manifest.json").write_text(
        json.dumps(
            {
                "frames": 10,
                "audit_outputs": [str(audit)],
                "deck": ["hog_rider"],
            }
        ),
        encoding="utf-8",
    )
    run = tmp_path / "derived" / "run_manifest.json"
    run.write_text(
        json.dumps(
            {
                "dataset": "owner/source",
                "records": [
                    {
                        "status": "complete",
                        "replay": "replay-a",
                        "arena": "arena_12",
                        "repo_path": str(repo_path),
                        "sha256": source_sha,
                        "size": source.stat().st_size,
                        "corpus": str(game / "corpus.npz"),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    card = tmp_path / "README.md"
    card.write_text("---\nlicense: mit\n---\n", encoding="utf-8")
    split = tmp_path / "split.json"
    split.write_text(
        json.dumps({"splits": {"train": {"replay_ids": ["replay-a"]}}}),
        encoding="utf-8",
    )
    return run, source_root, card, split


def test_plan_rejects_event_audits_as_percentage_evidence(tmp_path: Path) -> None:
    run, _, card, _ = _fixture(tmp_path)

    plan = build_reconstruction_plan(
        run_manifest=run,
        shard_count=1,
        dataset_card=card,
    )

    assert plan["local_evidence"]["retained_audit_images"] == 1
    assert plan["local_evidence"]["certified_percentage_fingerprints"] == 0
    assert plan["targets"][0]["missing_target_fractions"] == [0.1, 0.5, 0.9]
    assert plan["dataset_card"]["declared_license"] == "mit"
    assert plan["dataset_card"]["creative_commons_license_claimed"] is False


def test_local_exact_shard_verifies_source_and_builds_three_points(
    tmp_path: Path,
) -> None:
    run, source_root, card, split = _fixture(tmp_path)
    output = tmp_path / "shard.json"

    shard = reconstruct_shard(
        run_manifest=run,
        output=output,
        shard_count=1,
        shard_index=0,
        max_games=1,
        max_total_download_bytes=2_000_000_000,
        dataset_card=card,
        local_source_root=source_root,
    )

    assert shard["status"] == "complete"
    assert len(shard["entries"]) == 1
    entry = shard["entries"][0]
    assert [row["source_frame_id"] for row in entry["frames"]] == [7, 52, 83]
    assert all(len(row["normalized_frame_sha256"]) == 64 for row in entry["frames"])
    assert entry["permission_provenance"]["declared_license"] == "mit"
    assert entry["permission_provenance"][
        "creative_commons_license_claimed"
    ] is False

    artifacts, provenance = load_hf_fingerprint_shards(
        [output], run_manifests=[run], split_manifest=split
    )
    assert len(artifacts) == 1
    assert artifacts[0].proposed_split == "train"
    assert provenance["complete_source_coverage"] is True
