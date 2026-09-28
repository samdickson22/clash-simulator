"""Plan or execute bounded HF replay fingerprint reconstruction shards.

Each source replay is one large, single-row-group parquet whose image bytes are
stored in one dictionary page.  Exact random image access is therefore not
available.  This runner downloads at most one bounded hash shard, verifies the
historical source SHA-256, selects exact 10/50/90% rows by the public frame_id
clock, fingerprints the canonical arena crop, publishes atomically, and drops
the temporary parquet.
"""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
import io
import json
import re
import tempfile
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
from PIL import Image

from clasher.rl.oracle_corpus import atomic_write_json, file_sha256
from scripts.deduplicate_tv_royale_sources import TARGET_FRACTIONS, fingerprint_rgb

RAW_CROP_LEFT = 57
RAW_CROP_TOP = 137
RAW_CROP_WIDTH = 428
RAW_CROP_HEIGHT = 757
SOURCE_FPS = 10.0
DEFAULT_DATASET_ID = "chrisrca/clash-royale-tv-replays"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return payload


def _source_records(run_manifest: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _read_json(run_manifest)
    records = [
        dict(row)
        for row in payload.get("records", [])
        if isinstance(row, dict) and row.get("status") == "complete"
    ]
    records.sort(key=lambda row: str(row.get("replay")))
    if not records:
        raise ValueError("run manifest contains no completed source records")
    if len({str(row.get("replay")) for row in records}) != len(records):
        raise ValueError("run manifest contains duplicate completed replay IDs")
    for row in records:
        if not row.get("replay") or not row.get("repo_path") or not row.get("sha256"):
            raise ValueError("completed source record lacks replay/repo_path/SHA")
        if int(row.get("size", 0)) <= 0:
            raise ValueError(f"completed source record has invalid size: {row}")
    return payload, records


def _shard_for(replay: str, shard_count: int) -> int:
    digest = hashlib.sha256(replay.encode()).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def _dataset_card_provenance(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "path": None,
            "sha256": None,
            "declared_license": None,
            "creative_commons_license_claimed": False,
        }
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^license:\s*([^\s]+)\s*$", text)
    declared = match.group(1) if match else None
    return {
        "path": str(path.resolve()),
        "sha256": file_sha256(path),
        "declared_license": declared,
        "creative_commons_license_claimed": bool(
            declared and declared.casefold().startswith("cc-")
        ),
    }


def _game_manifest_path(record: Mapping[str, Any], run_manifest: Path) -> Path:
    corpus = record.get("corpus")
    if corpus:
        candidate = Path(str(corpus)).expanduser().resolve().parent / "manifest.json"
        if candidate.is_file():
            return candidate
    return (
        run_manifest.resolve().parent
        / "games"
        / str(record.get("arena"))
        / str(record.get("replay"))
        / "manifest.json"
    )


def _placement_rows(path: Path | None) -> dict[str, list[int]]:
    if path is None:
        return {}
    table = pq.read_table(path, columns=["replay", "frame"])
    result: dict[str, list[int]] = defaultdict(list)
    for replay, frame in zip(
        table.column("replay").to_pylist(),
        table.column("frame").to_pylist(),
        strict=True,
    ):
        result[str(replay)].append(int(frame))
    return dict(result)


def build_reconstruction_plan(
    *,
    run_manifest: Path,
    shard_count: int,
    dataset_card: Path | None = None,
    placement_parquet: Path | None = None,
) -> dict[str, Any]:
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    run, records = _source_records(run_manifest)
    placement = _placement_rows(placement_parquet)
    targets = []
    per_shard: Counter[int] = Counter()
    per_shard_bytes: Counter[int] = Counter()
    retained_audits = 0
    placement_overlap = 0
    for record in records:
        replay = str(record["replay"])
        shard = _shard_for(replay, shard_count)
        size = int(record["size"])
        per_shard[shard] += 1
        per_shard_bytes[shard] += size
        game_path = _game_manifest_path(record, run_manifest)
        audit_paths: list[str] = []
        if game_path.is_file():
            game = _read_json(game_path)
            audit_paths = [
                str(Path(str(path)).expanduser().resolve())
                for path in game.get("audit_outputs", [])
                if Path(str(path)).expanduser().is_file()
            ]
        retained_audits += len(audit_paths)
        replay_placement = sorted(placement.get(replay, []))
        placement_overlap += int(bool(replay_placement))
        targets.append(
            {
                "replay": replay,
                "arena": record.get("arena"),
                "shard_index": shard,
                "repo_path": record["repo_path"],
                "source_parquet_sha256": record["sha256"],
                "source_parquet_bytes": size,
                "missing_target_fractions": list(TARGET_FRACTIONS),
                "retained_game_manifest": (
                    str(game_path.resolve()) if game_path.is_file() else None
                ),
                "retained_audit_paths": audit_paths,
                "retained_audit_temporal_contract": (
                    "event-preferred extraction audit; not 10/50/90 evidence"
                ),
                "placement_png_rows": replay_placement,
                "placement_png_rows_are_target_fraction_evidence": False,
                "placement_limitation": (
                    "selected deployment frames lack the source sequence endpoints "
                    "needed to certify 10/50/90% positions"
                )
                if replay_placement
                else None,
            }
        )
    return {
        "schema": "tv-royale-hf-fingerprint-reconstruction-plan-v1",
        "status": "requires_bounded_network_shards",
        "source_run_manifest": {
            "path": str(run_manifest.resolve()),
            "sha256": file_sha256(run_manifest),
            "dataset_id": run.get("dataset", DEFAULT_DATASET_ID),
        },
        "dataset_card": _dataset_card_provenance(dataset_card),
        "target_contract": {
            "fractions": list(TARGET_FRACTIONS),
            "selection": "nearest source frame_id to fraction of [min,max]",
            "source_fps": SOURCE_FPS,
            "arena_crop_pixels_xywh": [
                RAW_CROP_LEFT,
                RAW_CROP_TOP,
                RAW_CROP_WIDTH,
                RAW_CROP_HEIGHT,
            ],
            "source_sha256_must_match": True,
            "hash_guessing_allowed": False,
        },
        "local_evidence": {
            "completed_replays": len(records),
            "retained_audit_images": retained_audits,
            "certified_percentage_fingerprints": 0,
            "placement_parquet": (
                {
                    "path": str(placement_parquet.resolve()),
                    "sha256": file_sha256(placement_parquet),
                    "overlapping_replays": placement_overlap,
                }
                if placement_parquet is not None
                else None
            ),
            "structured_npz_contains_source_pixels": False,
        },
        "network": {
            "files": len(records),
            "bytes_if_all_source_parquets_downloaded": sum(
                int(row["size"]) for row in records
            ),
            "reason_random_access_is_not_exact": (
                "sampled source parquets use one row group, one large "
                "image.bytes dictionary page, and no offset index"
            ),
        },
        "sharding": {
            "algorithm": "sha256(replay) first 64 bits modulo shard_count",
            "shard_count": shard_count,
            "games_per_shard": {str(key): per_shard[key] for key in range(shard_count)},
            "bytes_per_shard": {
                str(key): per_shard_bytes[key] for key in range(shard_count)
            },
        },
        "targets": targets,
    }


def _select_records(
    records: Sequence[dict[str, Any]],
    *,
    shard_count: int,
    shard_index: int,
    max_games: int | None,
    completed: set[str],
) -> list[dict[str, Any]]:
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must be within shard_count")
    selected = [
        row
        for row in records
        if _shard_for(str(row["replay"]), shard_count) == shard_index
        and str(row["replay"]) not in completed
    ]
    return selected[:max_games] if max_games is not None else selected


def _source_path(
    record: Mapping[str, Any],
    *,
    dataset_id: str,
    local_source_root: Path | None,
    temporary_root: Path,
) -> Path:
    repo_path = str(record["repo_path"])
    if local_source_root is not None:
        candidate = (local_source_root / repo_path).resolve()
        if candidate.is_file():
            return candidate
    from huggingface_hub import hf_hub_download

    return Path(
        hf_hub_download(
            repo_id=dataset_id,
            filename=repo_path,
            repo_type="dataset",
            cache_dir=temporary_root,
        )
    ).resolve()


def _selected_image_bytes(
    parquet: pq.ParquetFile, selected_rows: set[int]
) -> dict[int, bytes]:
    output: dict[int, bytes] = {}
    row_index = 0
    for batch in parquet.iter_batches(columns=["image"], batch_size=16, use_threads=False):
        for value in batch.column(0):
            if row_index in selected_rows:
                raw = value.as_py()
                if not isinstance(raw, dict) or not isinstance(raw.get("bytes"), bytes):
                    raise ValueError(f"invalid image payload at source row {row_index}")
                output[row_index] = raw["bytes"]
            row_index += 1
    if set(output) != selected_rows:
        raise ValueError("source parquet did not yield every selected image row")
    return output


def fingerprint_source_parquet(path: Path) -> tuple[float, list[dict[str, Any]]]:
    parquet = pq.ParquetFile(path)
    frame_table = parquet.read(columns=["frame_id"], use_threads=False)
    frame_ids = np.asarray(frame_table.column("frame_id").to_numpy(), dtype=np.int64)
    if frame_ids.ndim != 1 or frame_ids.size < 3:
        raise ValueError("source parquet has fewer than three frame IDs")
    if bool(np.any(np.diff(frame_ids) < 0)):
        raise ValueError("source frame IDs are not monotonically ordered")
    first = int(frame_ids[0])
    last = int(frame_ids[-1])
    if last <= first:
        raise ValueError("source frame clock does not advance")
    selected: list[tuple[float, int, float]] = []
    for fraction in TARGET_FRACTIONS:
        target = first + fraction * (last - first)
        row = int(np.argmin(np.abs(frame_ids - target)))
        selected.append((fraction, row, target))
    raw_images = _selected_image_bytes(parquet, {row for _, row, _ in selected})
    frames = []
    for fraction, row, target in selected:
        raw = raw_images[row]
        with Image.open(io.BytesIO(raw)) as loaded:
            rgb = np.asarray(loaded.convert("RGB"), dtype=np.uint8)
        bottom = RAW_CROP_TOP + RAW_CROP_HEIGHT
        right = RAW_CROP_LEFT + RAW_CROP_WIDTH
        if rgb.shape[0] < bottom or rgb.shape[1] < right:
            raise ValueError(f"source frame is too small for canonical crop: {rgb.shape}")
        crop = rgb[RAW_CROP_TOP:bottom, RAW_CROP_LEFT:right]
        frames.append(
            {
                "fraction": fraction,
                "selected_row_index": row,
                "source_frame_id": int(frame_ids[row]),
                "target_frame_id": target,
                "raw_png_sha256": hashlib.sha256(raw).hexdigest(),
                "arena_crop_pixels_xywh": [
                    RAW_CROP_LEFT,
                    RAW_CROP_TOP,
                    RAW_CROP_WIDTH,
                    RAW_CROP_HEIGHT,
                ],
                **fingerprint_rgb(crop),
            }
        )
    return (last - first) / SOURCE_FPS, frames


def reconstruct_shard(
    *,
    run_manifest: Path,
    output: Path,
    shard_count: int,
    shard_index: int,
    max_games: int | None,
    max_total_download_bytes: int,
    dataset_card: Path | None = None,
    local_source_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if max_total_download_bytes <= 0:
        raise ValueError("max_total_download_bytes must be positive")
    run, records = _source_records(run_manifest)
    run_sha = file_sha256(run_manifest)
    existing_entries: list[dict[str, Any]] = []
    if output.is_file() and not dry_run:
        previous = _read_json(output)
        if previous.get("source_run_manifest_sha256") != run_sha:
            raise ValueError("existing shard source manifest SHA changed")
        if previous.get("shard_count") != shard_count or previous.get(
            "shard_index"
        ) != shard_index:
            raise ValueError("existing shard identity changed")
        existing_entries = [dict(row) for row in previous.get("entries", [])]
    completed = {str(row.get("replay")) for row in existing_entries}
    selected = _select_records(
        records,
        shard_count=shard_count,
        shard_index=shard_index,
        max_games=max_games,
        completed=completed,
    )
    planned_bytes = sum(int(row["size"]) for row in selected)
    if planned_bytes > max_total_download_bytes:
        raise ValueError(
            f"selected shard needs {planned_bytes} bytes; limit is "
            f"{max_total_download_bytes}"
        )
    dataset_id = str(run.get("dataset") or DEFAULT_DATASET_ID)
    card = _dataset_card_provenance(dataset_card)
    payload: dict[str, Any] = {
        "schema": "tv-royale-hf-fingerprint-shard-v1",
        "status": "dry_run" if dry_run else "in_progress",
        "dataset_id": dataset_id,
        "dataset_card": card,
        "source_run_manifest": str(run_manifest.resolve()),
        "source_run_manifest_sha256": run_sha,
        "shard_count": shard_count,
        "shard_index": shard_index,
        "selected_remaining_games": len(selected),
        "planned_source_bytes": planned_bytes,
        "maximum_source_bytes": max_total_download_bytes,
        "entries": existing_entries,
        "planned": [
            {
                "replay": row["replay"],
                "repo_path": row["repo_path"],
                "source_parquet_sha256": row["sha256"],
                "source_parquet_bytes": row["size"],
            }
            for row in selected
        ],
    }
    if dry_run:
        atomic_write_json(output, payload)
        return payload
    started = time.monotonic()
    for record in selected:
        replay = str(record["replay"])
        with tempfile.TemporaryDirectory(prefix="clasher-hf-fingerprint-") as directory:
            source = _source_path(
                record,
                dataset_id=dataset_id,
                local_source_root=local_source_root,
                temporary_root=Path(directory),
            )
            actual_size = source.stat().st_size
            if actual_size != int(record["size"]):
                raise ValueError(f"source size mismatch for {replay}")
            actual_sha = file_sha256(source)
            if actual_sha != record["sha256"]:
                raise ValueError(f"source SHA-256 mismatch for {replay}")
            duration, frames = fingerprint_source_parquet(source)
        existing_entries.append(
            {
                "replay": replay,
                "arena": record.get("arena"),
                "repo_path": record["repo_path"],
                "source_parquet_sha256": actual_sha,
                "source_parquet_bytes": actual_size,
                "duration_seconds": duration,
                "decks": [],
                "players": [],
                "permission_provenance": {
                    "dataset_id": dataset_id,
                    "dataset_card_sha256": card["sha256"],
                    "declared_license": card["declared_license"],
                    "creative_commons_license_claimed": card[
                        "creative_commons_license_claimed"
                    ],
                },
                "frames": frames,
            }
        )
        payload["entries"] = existing_entries
        payload["completed_games"] = len(existing_entries)
        payload["elapsed_seconds"] = time.monotonic() - started
        atomic_write_json(output, payload)
    payload["status"] = "complete"
    payload["completed_games"] = len(existing_entries)
    payload["elapsed_seconds"] = time.monotonic() - started
    atomic_write_json(output, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-card", type=Path)
    parser.add_argument("--placement-parquet", type=Path)
    parser.add_argument("--shard-count", type=int, default=200)
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--max-games", type=int)
    parser.add_argument("--max-total-download-bytes", type=int, default=12_000_000_000)
    parser.add_argument("--local-source-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    if args.plan_only:
        payload = build_reconstruction_plan(
            run_manifest=args.run_manifest,
            shard_count=args.shard_count,
            dataset_card=args.dataset_card,
            placement_parquet=args.placement_parquet,
        )
        atomic_write_json(args.output, payload)
    else:
        if args.shard_index is None:
            parser.error("--shard-index is required outside --plan-only")
        payload = reconstruct_shard(
            run_manifest=args.run_manifest,
            output=args.output,
            shard_count=args.shard_count,
            shard_index=args.shard_index,
            max_games=args.max_games,
            max_total_download_bytes=args.max_total_download_bytes,
            dataset_card=args.dataset_card,
            local_source_root=args.local_source_root,
            dry_run=args.dry_run,
        )
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
