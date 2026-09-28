from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import numpy as np
import requests
from huggingface_hub import HfApi

from clasher.rl.imitation import load_corpus
from clasher.rl.imitation_mix import combine_imitation_corpora
from clasher.rl.oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256
from clasher.rl.public_observation import PUBLIC_OBSERVATION_SCHEMA_VERSION
from clasher.rl.replay_split import (
    STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE,
    combine_raw_cascade_location_corpora,
)

DATASET_ID = "chrisrca/clash-royale-tv-replays"
PUBLIC_STATE_ARRAYS = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "entity_id_confidence",
    "entity_feature_confidence",
    "hand_ids",
    "hand_id_confidence",
    "global_features",
    "global_feature_confidence",
    "opponent_history_ids",
    "opponent_history_ages",
    "opponent_history_confidence",
    "opponent_seen_card_ids",
    "opponent_seen_card_confidence",
)
PUBLIC_ALIGNMENT_ARRAYS = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "hand_ids",
    "global_features",
    "action_masks",
    "expert_actions",
)


@dataclass(frozen=True)
class ReplaySource:
    arena: str
    replay: str
    repo_path: str
    size: int
    sha256: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stream, extract, validate, and delete raw TV Royale replays with "
            "one-download lookahead"
        )
    )
    parser.add_argument("--target-games", type=int, default=1000)
    parser.add_argument("--max-attempts", type=int, default=1600)
    parser.add_argument("--arena-min", type=int, default=12)
    parser.add_argument("--arena-max", type=int, default=31)
    parser.add_argument("--seed", type=int, default=1_044_201)
    parser.add_argument(
        "--scratch-dir", default="datasets/external/tv_royale_raw_stream"
    )
    parser.add_argument(
        "--output-dir", default="datasets/derived/tv_royale_raw_cascade_1000"
    )
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument(
        "--ui-template-root",
        default="datasets/external/CS541-Deep-Learning-Clash-Royale-Project",
    )
    parser.add_argument("--katacr-source-root", default="datasets/external/KataCR")
    parser.add_argument("--detector-weight", action="append", required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--noop-stride", type=int, default=20)
    parser.add_argument("--terminal-noop-exclusion", type=int, default=50)
    parser.add_argument("--audit-samples", type=int, default=2)
    parser.add_argument("--download-retries", type=int, default=4)
    parser.add_argument(
        "--exclude-replay",
        action="append",
        default=[
            "25848212-ea7a-48c9-bd4a-f1c27206396f",
            "d0417583-846d-4659-8d3b-54e0318084ed",
        ],
    )
    parser.add_argument(
        "--exclude-run-manifest",
        action="append",
        default=[],
        help=(
            "repeat to exclude every completed replay in a prior raw-cascade "
            "run; this creates a replay-disjoint extraction wave"
        ),
    )
    return parser.parse_args()


def completed_replays_from_manifests(paths: list[str]) -> set[str]:
    """Load completed replay IDs used by earlier extraction waves."""
    completed: set[str] = set()
    for value in paths:
        path = Path(value).resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("records")
        if not isinstance(records, list):
            raise TypeError(f"exclude run manifest has no records: {path}")
        completed.update(
            str(record["replay"])
            for record in records
            if isinstance(record, dict)
            and record.get("status") == "complete"
            and record.get("replay")
        )
    return completed


def _source_inventory(
    *, arena_min: int, arena_max: int, seed: int, excluded: set[str]
) -> list[ReplaySource]:
    by_arena: dict[str, list[ReplaySource]] = {}
    for item in HfApi().list_repo_tree(
        DATASET_ID, repo_type="dataset", recursive=True
    ):
        repo_path = getattr(item, "path", "")
        if not repo_path.endswith("/frames.parquet"):
            continue
        arena, replay, _ = repo_path.split("/")
        arena_number = int(arena.removeprefix("arena_"))
        if not arena_min <= arena_number <= arena_max or replay in excluded:
            continue
        lfs = getattr(item, "lfs", None)
        sha256 = str(getattr(lfs, "sha256", ""))
        if len(sha256) != 64:
            raise ValueError(f"source {repo_path} has no pinned LFS SHA-256")
        by_arena.setdefault(arena, []).append(
            ReplaySource(
                arena=arena,
                replay=replay,
                repo_path=repo_path,
                size=int(getattr(item, "size", 0) or 0),
                sha256=sha256,
            )
        )
    rng = random.Random(seed)
    for values in by_arena.values():
        rng.shuffle(values)
    queue: list[ReplaySource] = []
    arenas = sorted(by_arena)
    cursor = 0
    while True:
        added = False
        for arena in arenas:
            if cursor < len(by_arena[arena]):
                queue.append(by_arena[arena][cursor])
                added = True
        if not added:
            break
        cursor += 1
    return queue


def _download(
    source: ReplaySource,
    scratch_root: Path,
    *,
    retries: int,
) -> tuple[Path, float]:
    target = scratch_root / source.arena / source.replay / "frames.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size == source.size:
        if file_sha256(target) == source.sha256:
            return target, 0.0
        target.unlink()
    partial = target.with_suffix(".parquet.part")
    url = (
        f"https://huggingface.co/datasets/{DATASET_ID}/resolve/main/"
        f"{quote(source.repo_path, safe='/')}?download=true"
    )
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        started = time.perf_counter()
        digest = hashlib.sha256()
        try:
            with requests.get(url, stream=True, timeout=(30, 300)) as response:
                response.raise_for_status()
                with partial.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                        if not chunk:
                            continue
                        output.write(chunk)
                        digest.update(chunk)
                    output.flush()
                    os.fsync(output.fileno())
            if partial.stat().st_size != source.size:
                raise ValueError(
                    f"downloaded {partial.stat().st_size} bytes; expected {source.size}"
                )
            if digest.hexdigest() != source.sha256:
                raise ValueError("download SHA-256 does not match the repository LFS pin")
            os.replace(partial, target)
            return target, time.perf_counter() - started
        except Exception as error:  # noqa: BLE001 - retry and record transport failures
            last_error = error
            partial.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(min(10.0, 2.0**attempt))
    assert last_error is not None
    raise last_error


def _extract_command(args: argparse.Namespace, source: ReplaySource, path: Path) -> list[str]:
    command = [
        sys.executable,
        "scripts/extract_tv_royale_raw_cascade.py",
        "--input-parquet",
        str(path),
        "--arena",
        source.arena,
        "--replay",
        source.replay,
        "--output-dir",
        str(Path(args.output_dir).resolve() / "games"),
        "--decks-path",
        args.decks_path,
        "--ui-template-root",
        args.ui_template_root,
        "--katacr-source-root",
        args.katacr_source_root,
        "--device",
        args.device,
        "--batch-size",
        str(args.batch_size),
        "--noop-stride",
        str(args.noop_stride),
        "--terminal-noop-exclusion",
        str(args.terminal_noop_exclusion),
        "--audit-samples",
        str(args.audit_samples),
        "--seed",
        str(args.seed),
    ]
    for weight in args.detector_weight:
        command.extend(("--detector-weight", weight))
    return command


def _remove_raw(path: Path, scratch_root: Path) -> None:
    path.unlink(missing_ok=True)
    parent = path.parent
    while parent != scratch_root and parent.is_relative_to(scratch_root):
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def _write_run_manifest(
    path: Path,
    *,
    args: argparse.Namespace,
    queue: list[ReplaySource],
    records: list[dict[str, Any]],
    started: float,
    initial_completed_games: int,
) -> None:
    completed = [record for record in records if record["status"] == "complete"]
    failed = [record for record in records if record["status"] == "failed"]
    elapsed = time.perf_counter() - started
    session_completed = max(0, len(completed) - initial_completed_games)
    payload = {
        "schema": "tv-royale-raw-cascade-run-v1",
        "dataset": DATASET_ID,
        "seed": args.seed,
        "target_games": args.target_games,
        "max_attempts": args.max_attempts,
        "arenas": [args.arena_min, args.arena_max],
        "inventory_games": len(queue),
        "completed_games": len(completed),
        "session_initial_completed_games": initial_completed_games,
        "session_completed_games": session_completed,
        "failed_games": len(failed),
        "attempted_games": len(records),
        "elapsed_seconds": elapsed,
        "observed_completed_games_per_hour": (
            session_completed * 3600.0 / elapsed if elapsed > 0.0 else 0.0
        ),
        "raw_retention": "deleted after corpus and manifest validation",
        "records": records,
    }
    atomic_write_json(path, payload)


def _pending_sources(
    queue: list[ReplaySource], records: list[dict[str, Any]]
) -> list[ReplaySource]:
    """Resume only sources that have never produced a terminal run record."""
    attempted_ids = {
        str(record["replay"])
        for record in records
        if record.get("status") in {"complete", "failed"}
    }
    return [source for source in queue if source.replay not in attempted_ids]


def _validated_game_result(
    output_root: Path, source: ReplaySource
) -> tuple[Path, dict[str, Any]]:
    game_root = output_root / "games" / source.arena / source.replay
    manifest_path = game_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    corpus_path = game_root / "corpus.npz"
    if file_sha256(corpus_path) != manifest["corpus"]["sha256"]:
        raise ValueError("published game corpus does not match its manifest digest")
    metadata, arrays = load_corpus(corpus_path)
    if metadata.samples <= 0 or arrays["expert_actions"].shape[0] != metadata.samples:
        raise ValueError("published game corpus is empty or structurally invalid")
    public_manifest = manifest.get("public_state_v2")
    if public_manifest is not None:
        public_path = Path(public_manifest["path"])
        if file_sha256(public_path) != public_manifest["sha256"]:
            raise ValueError("published public-state sidecar digest does not match")
        with (
            np.load(public_path, allow_pickle=False) as public,
            np.load(corpus_path, allow_pickle=False) as full_corpus,
        ):
            if int(public["schema_version"].item()) != PUBLIC_OBSERVATION_SCHEMA_VERSION:
                raise ValueError("published public-state sidecar schema does not match")
            if not np.array_equal(
                public["expert_actions"], full_corpus["expert_actions"]
            ):
                raise ValueError("published public-state sidecar actions are not aligned")
            if not np.array_equal(
                public["source_frames"], full_corpus["source_frames"]
            ):
                raise ValueError("published public-state sidecar frames are not aligned")
            if not np.array_equal(
                public["source_indices"], full_corpus["source_indices"]
            ):
                raise ValueError("published public-state sidecar indices are not aligned")
    return corpus_path, manifest


def _combine_public_state_v2(
    *,
    records: list[dict[str, Any]],
    combined_corpus_path: Path,
    output_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """Align per-game v2 observations to the deduplicated combined corpus."""

    with np.load(combined_corpus_path, allow_pickle=False) as combined:
        combined_identity = {
            name: combined[name].copy() for name in PUBLIC_ALIGNMENT_ARRAYS
        }
        combined_actions = combined["expert_actions"].copy()
        combined_episode_ids = combined["episode_ids"].copy()
    canonical_dtypes = {
        name: values.dtype for name, values in combined_identity.items()
    }

    def fingerprint(arrays: dict[str, np.ndarray], row: int) -> bytes:
        digest = hashlib.sha256()
        for name in PUBLIC_ALIGNMENT_ARRAYS:
            value = np.ascontiguousarray(
                arrays[name][row], dtype=canonical_dtypes[name]
            )
            digest.update(name.encode("ascii"))
            digest.update(value.dtype.str.encode("ascii"))
            digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
            digest.update(value.tobytes())
        return digest.digest()

    public_chunks: dict[str, list[np.ndarray]] = {
        name: [] for name in PUBLIC_STATE_ARRAYS
    }
    replay_chunks: list[np.ndarray] = []
    index_chunks: list[np.ndarray] = []
    frame_chunks: list[np.ndarray] = []
    action_chunks: list[np.ndarray] = []
    row_by_fingerprint: dict[bytes, int] = {}
    source_row_offset = 0
    for record in records:
        corpus_path = Path(record["corpus"])
        public_path = Path(record["public_state_v2"])
        with (
            np.load(corpus_path, allow_pickle=False) as corpus,
            np.load(public_path, allow_pickle=False) as public,
        ):
            if int(public["schema_version"].item()) != PUBLIC_OBSERVATION_SCHEMA_VERSION:
                raise ValueError(f"unsupported public-state schema in {public_path}")
            for name in PUBLIC_STATE_ARRAYS:
                if name not in public:
                    raise ValueError(f"public-state sidecar {public_path} lacks {name}")
                public_chunks[name].append(public[name].copy())
            for name in ("source_indices", "source_frames", "expert_actions"):
                if not np.array_equal(public[name], corpus[name]):
                    raise ValueError(
                        f"public-state sidecar {public_path} is not aligned on {name}"
                    )
            replay_chunks.append(corpus["source_replays"].copy())
            index_chunks.append(corpus["source_indices"].copy())
            frame_chunks.append(corpus["source_frames"].copy())
            action_chunks.append(corpus["expert_actions"].copy())
            corpus_identity = {
                name: corpus[name].copy() for name in PUBLIC_ALIGNMENT_ARRAYS
            }
            for row in range(corpus["expert_actions"].shape[0]):
                row_by_fingerprint.setdefault(
                    fingerprint(corpus_identity, row), source_row_offset + row
                )
            source_row_offset += int(corpus["expert_actions"].shape[0])

    source_replays = np.concatenate(replay_chunks)
    source_indices = np.concatenate(index_chunks)
    source_frames = np.concatenate(frame_chunks)
    source_actions = np.concatenate(action_chunks)
    combined_rows = int(combined_actions.shape[0])
    try:
        selection = np.asarray(
            [
                row_by_fingerprint[fingerprint(combined_identity, row)]
                for row in range(combined_rows)
            ],
            dtype=np.int64,
        )
    except KeyError as error:
        raise ValueError(
            "combined corpus row has no exact public-state source fingerprint"
        ) from error
    if np.unique(selection).size != selection.size:
        raise ValueError("combined public-state alignment selected a source row twice")
    if not np.array_equal(source_actions[selection], combined_actions):
        raise ValueError("combined public-state expert actions are not aligned")
    payload = {
        name: np.concatenate(chunks)[selection]
        for name, chunks in public_chunks.items()
    }
    payload.update(
        {
            "source_replays": source_replays[selection],
            "source_indices": source_indices[selection],
            "source_frames": source_frames[selection],
            "expert_actions": combined_actions,
            "episode_ids": combined_episode_ids,
            "schema_version": np.asarray(PUBLIC_OBSERVATION_SCHEMA_VERSION),
        }
    )
    atomic_save_npz(output_path, payload)
    visible = payload["entity_mask"].astype(np.bool_, copy=False)
    hp = (payload["entity_feature_confidence"][..., 9] > 0.0) & visible
    motion = (payload["entity_feature_confidence"][..., 27] > 0.0) & visible
    manifest = {
        "schema": "combined-confidence-aware-public-observation-v2",
        "schema_version": PUBLIC_OBSERVATION_SCHEMA_VERSION,
        "source_games": len(records),
        "samples": int(selection.size),
        "visible_entities": int(visible.sum()),
        "entities_with_hp": int(hp.sum()),
        "entity_hp_coverage": float(hp.sum() / max(1, int(visible.sum()))),
        "entities_with_motion": int(motion.sum()),
        "motion_coverage": float(motion.sum() / max(1, int(visible.sum()))),
        "output": str(output_path),
        "output_sha256": file_sha256(output_path),
        "combined_corpus": str(combined_corpus_path),
        "combined_corpus_sha256": file_sha256(combined_corpus_path),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def _publish_combined_corpora(
    *,
    args: argparse.Namespace,
    output_root: Path,
    run_manifest_path: Path,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    successful = [record for record in records if record["status"] == "complete"]
    sources = [Path(record["corpus"]) for record in successful[: args.target_games]]
    combined_stem = f"tv_royale_raw_cascade_{args.target_games}"
    combined_path = output_root / f"{combined_stem}.npz"
    combined_manifest = output_root / f"{combined_stem}_manifest.json"
    combine_imitation_corpora(
        sources=sources,
        output_path=combined_path,
        manifest_path=combined_manifest,
        seed=args.seed,
        deduplicate=True,
    )
    selected_records = successful[: args.target_games]
    public_records = [record for record in selected_records if record.get("public_state_v2")]
    if public_records and len(public_records) != len(selected_records):
        raise ValueError("only some completed games contain public-state v2 sidecars")
    public_manifest: dict[str, Any] | None = None
    public_path = output_root / f"{combined_stem}_public_state_v2.npz"
    public_manifest_path = (
        output_root / f"{combined_stem}_public_state_v2_manifest.json"
    )
    if public_records:
        public_manifest = _combine_public_state_v2(
            records=public_records,
            combined_corpus_path=combined_path,
            output_path=public_path,
            manifest_path=public_manifest_path,
        )
    location_path = output_root / f"{combined_stem}_locations.npz"
    location_manifest_path = output_root / f"{combined_stem}_locations_manifest.json"
    location_manifest: dict[str, Any] | None = None
    try:
        location_manifest = combine_raw_cascade_location_corpora(
            run_manifest_path=run_manifest_path,
            output_path=location_path,
            manifest_path=location_manifest_path,
            seed=args.seed,
            target_games=args.target_games,
            required_label_source=STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE,
        )
    except ValueError as error:
        if "contains no valid location sidecars" not in str(error):
            raise
    return {
        "combined": str(combined_path),
        "sha256": file_sha256(combined_path),
        "location_combined": str(location_path) if location_manifest else None,
        "location_sha256": file_sha256(location_path) if location_manifest else None,
        "location_samples": (
            int(location_manifest["samples"]) if location_manifest else 0
        ),
        "public_state_v2_combined": str(public_path) if public_manifest else None,
        "public_state_v2_sha256": (
            str(public_manifest["output_sha256"]) if public_manifest else None
        ),
        "public_state_v2_samples": (
            int(public_manifest["samples"]) if public_manifest else 0
        ),
    }


def main() -> None:
    args = parse_args()
    if args.target_games <= 0 or args.max_attempts < args.target_games:
        raise ValueError("target must be positive and max attempts must cover target")
    output_root = Path(args.output_dir).resolve()
    scratch_root = Path(args.scratch_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    scratch_root.mkdir(parents=True, exist_ok=True)
    run_manifest_path = output_root / "run_manifest.json"
    excluded_replays = set(args.exclude_replay)
    excluded_replays.update(
        completed_replays_from_manifests(args.exclude_run_manifest)
    )
    queue = _source_inventory(
        arena_min=args.arena_min,
        arena_max=args.arena_max,
        seed=args.seed,
        excluded=excluded_replays,
    )
    if len(queue) < args.target_games:
        raise ValueError("selected arena range does not contain enough games")
    records: list[dict[str, Any]] = []
    completed_ids: set[str] = set()
    if run_manifest_path.is_file():
        previous = json.loads(run_manifest_path.read_text())
        records = list(previous.get("records", []))
        completed_ids = {
            str(record["replay"])
            for record in records
            if record.get("status") == "complete"
        }
    pending = _pending_sources(queue, records)
    started = time.perf_counter()
    completed_count = len(completed_ids)
    initial_completed_games = completed_count
    attempts = len(records)
    if completed_count >= args.target_games:
        published = _publish_combined_corpora(
            args=args,
            output_root=output_root,
            run_manifest_path=run_manifest_path,
            records=records,
        )
        print(
            json.dumps(
                {"status": "already_complete", "games": completed_count, **published},
                sort_keys=True,
            )
        )
        return

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="tv-download") as pool:
        source_index = 0
        current_source = pending[source_index]
        current_download: Future[tuple[Path, float]] = pool.submit(
            _download,
            current_source,
            scratch_root,
            retries=args.download_retries,
        )
        while (
            completed_count < args.target_games
            and attempts < args.max_attempts
            and source_index < len(pending)
        ):
            source = current_source
            record: dict[str, Any] = {
                **asdict(source),
                "attempt": attempts + 1,
                "started_at_unix": time.time(),
            }
            try:
                raw_path, download_seconds = current_download.result()
                record["download_seconds"] = download_seconds
                next_source: ReplaySource | None = None
                next_download: Future[tuple[Path, float]] | None = None
                if source_index + 1 < len(pending):
                    next_source = pending[source_index + 1]
                    next_download = pool.submit(
                        _download,
                        next_source,
                        scratch_root,
                        retries=args.download_retries,
                    )
                log_dir = output_root / "logs" / source.arena
                log_dir.mkdir(parents=True, exist_ok=True)
                log_path = log_dir / f"{source.replay}.log"
                extract_started = time.perf_counter()
                with log_path.open("wb") as log:
                    result = subprocess.run(
                        _extract_command(args, source, raw_path),
                        cwd=Path(__file__).resolve().parents[1],
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        check=False,
                    )
                record["extract_seconds"] = time.perf_counter() - extract_started
                record["extract_returncode"] = result.returncode
                record["log"] = str(log_path)
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args)
                corpus_path, game_manifest = _validated_game_result(output_root, source)
                record.update(
                    {
                        "status": "complete",
                        "corpus": str(corpus_path),
                        "corpus_sha256": game_manifest["corpus"]["sha256"],
                        "samples": game_manifest["corpus"]["statistics"]["samples"],
                        "accepted_type_events": game_manifest["accepted_type_events"],
                        "accepted_noops": game_manifest["accepted_noops"],
                        "selected_vision_frames": game_manifest["selected_vision_frames"],
                        "public_state_v2": game_manifest["public_state_v2"]["path"],
                        "public_state_v2_sha256": game_manifest["public_state_v2"][
                            "sha256"
                        ],
                    }
                )
                completed_count += 1
                _remove_raw(raw_path, scratch_root)
                record["raw_deleted"] = True
            except Exception as error:  # noqa: BLE001 - fail one replay, continue run
                record.update(
                    {
                        "status": "failed",
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                )
                raw_path = scratch_root / source.arena / source.replay / "frames.parquet"
                _remove_raw(raw_path, scratch_root)
                record["raw_deleted"] = True
                next_source = None
                next_download = None
            records.append(record)
            attempts += 1
            _write_run_manifest(
                run_manifest_path,
                args=args,
                queue=queue,
                records=records,
                started=started,
                initial_completed_games=initial_completed_games,
            )
            print(
                json.dumps(
                    {
                        "attempts": attempts,
                        "completed": completed_count,
                        "target": args.target_games,
                        "last": record,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if completed_count >= args.target_games:
                if next_download is not None:
                    try:
                        prefetched_path, _ = next_download.result()
                        _remove_raw(prefetched_path, scratch_root)
                    except Exception as error:  # noqa: BLE001 - owned scratch cleanup
                        print(
                            json.dumps(
                                {
                                    "warning": "prefetch_cleanup_failed",
                                    "error": str(error),
                                }
                            ),
                            flush=True,
                        )
                break
            source_index += 1
            if source_index >= len(pending):
                break
            if next_download is None or next_source != pending[source_index]:
                current_source = pending[source_index]
                current_download = pool.submit(
                    _download,
                    current_source,
                    scratch_root,
                    retries=args.download_retries,
                )
            else:
                current_source = next_source
                current_download = next_download

    if completed_count < args.target_games:
        raise RuntimeError(
            f"only {completed_count}/{args.target_games} games completed after "
            f"{attempts} attempts"
        )
    published = _publish_combined_corpora(
        args=args,
        output_root=output_root,
        run_manifest_path=run_manifest_path,
        records=records,
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "games": args.target_games,
                **published,
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
